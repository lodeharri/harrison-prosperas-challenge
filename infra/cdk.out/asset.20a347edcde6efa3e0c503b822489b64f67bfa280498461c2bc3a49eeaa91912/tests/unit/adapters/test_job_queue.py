"""Tests for SQS JobQueue adapter."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json

from backend.src.adapters.secondary.sqs.job_queue import (
    SQSJobQueue,
    HIGH_PRIORITY_REPORT_TYPES,
)
from backend.src.domain.entities.job import Job
from backend.src.domain.value_objects.job_status import JobStatus


class TestSQSJobQueuePublish:
    """Tests for publish() method."""

    def test_publish_success(self, mock_settings):
        """Test publishing a job successfully."""
        queue = SQSJobQueue(settings=mock_settings)
        mock_client = MagicMock()
        queue._client = mock_client

        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
            date_range="2024-01-01 to 2024-01-31",
            format="pdf",
        )

        result = queue.publish(job)

        assert result is True
        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args.kwargs
        assert "QueueUrl" in call_kwargs
        assert "MessageBody" in call_kwargs
        assert "MessageAttributes" in call_kwargs

    def test_publish_client_error(self, mock_settings):
        """Test publish raises on ClientError."""
        from botocore.exceptions import ClientError

        queue = SQSJobQueue(settings=mock_settings)
        mock_client = MagicMock()
        mock_client.send_message.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test"}}, "SendMessage"
        )
        queue._client = mock_client

        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )

        with pytest.raises(ClientError):
            queue.publish(job)

    def test_publish_includes_message_attributes(self, mock_settings):
        """Test publish includes correct message attributes."""
        queue = SQSJobQueue(settings=mock_settings)
        mock_client = MagicMock()
        queue._client = mock_client

        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="inventory_report",
        )

        queue.publish(job)

        call_kwargs = mock_client.send_message.call_args.kwargs
        message_attrs = call_kwargs["MessageAttributes"]
        assert message_attrs["ReportType"]["DataType"] == "String"
        assert message_attrs["ReportType"]["StringValue"] == "inventory_report"


class TestSQSJobQueuePublishPriority:
    """Tests for publish_priority() method."""

    @pytest.mark.asyncio
    async def test_publish_priority_success(self, mock_settings):
        """Test publishing a high-priority job successfully."""
        queue = SQSJobQueue(settings=mock_settings)
        mock_client = MagicMock()
        queue._client = mock_client

        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
            date_range="2024-01-01 to 2024-01-31",
            format="excel",
        )

        result = await queue.publish_priority(job)

        assert result is True
        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args.kwargs
        assert "QueueUrl" in call_kwargs
        assert "MessageBody" in call_kwargs
        # Check priority is included in message body
        body = json.loads(call_kwargs["MessageBody"])
        assert body["priority"] == "high"
        assert body["report_type"] == "sales_report"

    @pytest.mark.asyncio
    async def test_publish_priority_client_error(self, mock_settings):
        """Test publish_priority raises on ClientError."""
        from botocore.exceptions import ClientError

        queue = SQSJobQueue(settings=mock_settings)
        mock_client = MagicMock()
        mock_client.send_message.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test"}}, "SendMessage"
        )
        queue._client = mock_client

        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="financial_report",
        )

        with pytest.raises(ClientError):
            await queue.publish_priority(job)

    @pytest.mark.asyncio
    async def test_publish_priority_includes_created_at(self, mock_settings):
        """Test publish_priority includes created_at in message body."""
        queue = SQSJobQueue(settings=mock_settings)
        mock_client = MagicMock()
        queue._client = mock_client

        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )

        await queue.publish_priority(job)

        call_kwargs = mock_client.send_message.call_args.kwargs
        body = json.loads(call_kwargs["MessageBody"])
        assert "created_at" in body


class TestSQSJobQueueSendToQueue:
    """Tests for _send_to_queue() method."""

    @pytest.mark.asyncio
    async def test_send_to_queue(self, mock_settings):
        """Test _send_to_queue sends correct message."""
        queue = SQSJobQueue(settings=mock_settings)
        mock_client = MagicMock()
        queue._client = mock_client

        await queue._send_to_queue(
            queue_url="https://example.com/queue",
            message_body='{"test": "data"}',
            job_id="test-123",
            report_type="sales_report",
            priority="high",
        )

        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args.kwargs
        assert call_kwargs["QueueUrl"] == "https://example.com/queue"
        assert call_kwargs["MessageBody"] == '{"test": "data"}'
        message_attrs = call_kwargs["MessageAttributes"]
        assert message_attrs["priority"]["StringValue"] == "high"
        assert message_attrs["report_type"]["StringValue"] == "sales_report"


class TestSQSJobQueueHealthCheck:
    """Tests for health_check() method."""

    def test_health_check_success(self, mock_settings):
        """Test health_check returns True when healthy."""
        queue = SQSJobQueue(settings=mock_settings)
        mock_client = MagicMock()
        queue._client = mock_client

        result = queue.health_check()

        assert result is True
        mock_client.get_queue_url.assert_called_once()

    def test_health_check_failure(self, mock_settings):
        """Test health_check returns False on ClientError."""
        from botocore.exceptions import ClientError

        queue = SQSJobQueue(settings=mock_settings)
        mock_client = MagicMock()
        mock_client.get_queue_url.side_effect = ClientError(
            {"Error": {"Code": "QueueDoesNotExist", "Message": "Test"}}, "GetQueueUrl"
        )
        queue._client = mock_client

        result = queue.health_check()

        assert result is False


class TestSQSJobQueueClientProperty:
    """Tests for client property with lazy initialization."""

    def test_client_lazy_initialization(self, mock_settings):
        """Test client is initialized on first access."""
        queue = SQSJobQueue(settings=mock_settings)

        # Client should be None initially
        assert queue._client is None

        # Access client property
        with patch("backend.src.adapters.secondary.sqs.job_queue.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            client = queue.client

            # Should have called boto3.client
            mock_boto3.client.assert_called_once()
            assert client is not None

    def test_client_reuse(self, mock_settings):
        """Test client is reused on subsequent access."""
        queue = SQSJobQueue(settings=mock_settings)

        with patch("backend.src.adapters.secondary.sqs.job_queue.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            # Access client twice
            client1 = queue.client
            client2 = queue.client

            # Should only call boto3.client once
            assert mock_boto3.client.call_count == 1
            assert client1 is client2


class TestHighPriorityReportTypes:
    """Tests for HIGH_PRIORITY_REPORT_TYPES constant."""

    def test_high_priority_types_defined(self):
        """Test high priority report types are defined."""
        assert "sales_report" in HIGH_PRIORITY_REPORT_TYPES
        assert "financial_report" in HIGH_PRIORITY_REPORT_TYPES
        assert len(HIGH_PRIORITY_REPORT_TYPES) == 2

    def test_other_types_not_high_priority(self):
        """Test other report types are not high priority."""
        assert "inventory_report" not in HIGH_PRIORITY_REPORT_TYPES
        assert "hr_report" not in HIGH_PRIORITY_REPORT_TYPES
