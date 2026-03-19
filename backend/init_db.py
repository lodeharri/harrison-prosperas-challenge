#!/usr/bin/env python3
"""DynamoDB table initialization script.

This script creates the required DynamoDB tables for the report job processing system.
Run this script before starting the application to set up the database.

Usage:
    python init_db.py

Environment Variables:
    AWS_ENDPOINT_URL: LocalStack endpoint (default: http://localhost:4566)
    AWS_REGION: AWS region (default: us-east-1)
    AWS_ACCESS_KEY_ID: AWS access key (default: test)
    AWS_SECRET_ACCESS_KEY: AWS secret key (default: test)
    DYNAMODB_TABLE_JOBS: Jobs table name (default: jobs)
"""

import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_config() -> dict:
    """Get configuration from environment variables."""
    return {
        "endpoint_url": os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
        "region_name": os.getenv("AWS_REGION", "us-east-1"),
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID", "test"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        "table_name": os.getenv("DYNAMODB_TABLE_JOBS", "jobs"),
        "idempotency_table_name": os.getenv(
            "DYNAMODB_TABLE_IDEMPOTENCY", "idempotency_keys"
        ),
        "queue_name": os.getenv("SQS_QUEUE_NAME", "report-jobs-queue"),
        "dlq_name": os.getenv("SQS_DLQ_NAME", "report-jobs-dlq"),
    }


def create_dynamodb_table(dynamodb: Any, table_name: str) -> bool:
    """
    Create the jobs table with GSI for user_id lookups.

    Args:
        dynamodb: Boto3 DynamoDB client
        table_name: Name for the jobs table

    Returns:
        True if table was created or already exists
    """
    try:
        # Check if table already exists
        try:
            response = dynamodb.describe_table(TableName=table_name)
            logger.info(f"Table '{table_name}' already exists")
            return True
        except dynamodb.exceptions.ResourceNotFoundException:
            pass

        # Create table with GSI for user_id lookups
        # Note: Idempotency keys are now stored in a separate table
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "job_id", "KeyType": "HASH"},  # Partition key
            ],
            AttributeDefinitions=[
                {"AttributeName": "job_id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-created_at-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                },
            ],
            ProvisionedThroughput={
                "ReadCapacityUnits": 5,
                "WriteCapacityUnits": 5,
            },
        )

        # Wait for table to be active
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=table_name)
        logger.info(
            f"Created table '{table_name}' with GSI: 'user_id-created_at-index'"
        )
        return True

    except ClientError as e:
        logger.error(f"Failed to create table '{table_name}': {e}")
        return False


def create_idempotency_table(dynamodb: Any, table_name: str) -> bool:
    """
    Create the idempotency_keys table with TTL support.

    This table stores idempotency keys separately from jobs to ensure
    that TTL expiration only removes the key reference, not the entire job.

    Table Design:
    - Primary Key: idempotency_key (String) - the key provided by the client
    - Attributes:
        - job_id: Reference to the associated job
        - created_at: Timestamp when the key was created
    - TTL: expires_at attribute for automatic cleanup

    Args:
        dynamodb: Boto3 DynamoDB client
        table_name: Name for the idempotency keys table

    Returns:
        True if table was created or already exists
    """
    try:
        # Check if table already exists
        try:
            response = dynamodb.describe_table(TableName=table_name)
            logger.info(f"Idempotency table '{table_name}' already exists")

            # Check if TTL attribute needs to be enabled
            ttl_description = response["Table"].get("TimeToLiveDescription", {})
            if not ttl_description.get("AttributeName"):
                logger.info("Enabling TTL on idempotency table...")
                dynamodb.update_time_to_live(
                    TableName=table_name,
                    TimeToLiveSpecification={
                        "Enabled": True,
                        "AttributeName": "expires_at",
                    },
                )
                logger.info("Enabled TTL on idempotency table")

            return True
        except dynamodb.exceptions.ResourceNotFoundException:
            pass

        # Create the idempotency keys table
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "idempotency_key", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "idempotency_key", "AttributeType": "S"},
            ],
            ProvisionedThroughput={
                "ReadCapacityUnits": 5,
                "WriteCapacityUnits": 5,
            },
        )

        # Wait for table to be active
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=table_name)
        logger.info(f"Created idempotency table '{table_name}'")

        # Enable TTL on the table
        dynamodb.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={
                "Enabled": True,
                "AttributeName": "expires_at",
            },
        )
        logger.info(f"Enabled TTL on idempotency table '{table_name}'")

        return True

    except ClientError as e:
        logger.error(f"Failed to create idempotency table '{table_name}': {e}")
        return False


def create_sqs_queue(sqs: Any, queue_name: str, dlq_name: str) -> tuple[str, str]:
    """
    Create the SQS queue and dead letter queue.

    Args:
        sqs: Boto3 SQS client
        queue_name: Name for the main queue
        dlq_name: Name for the dead letter queue

    Returns:
        Tuple of (queue_url, dlq_url)
    """
    try:
        # Check if queue already exists
        try:
            response = sqs.get_queue_url(QueueName=queue_name)
            queue_url = response["QueueUrl"]
            logger.info(f"Queue '{queue_name}' already exists: {queue_url}")
        except sqs.exceptions.QueueDoesNotExist:
            # Create main queue with DLQ configuration
            dlq_response = sqs.create_queue(
                QueueName=dlq_name,
                Attributes={
                    "VisibilityTimeout": "30",
                },
            )
            dlq_url = dlq_response["QueueUrl"]
            logger.info(f"Created DLQ '{dlq_name}': {dlq_url}")

            # Get DLQ ARN for main queue redrive policy
            dlq_attributes = sqs.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=["QueueArn"],
            )
            dlq_arn = dlq_attributes["Attributes"]["QueueArn"]

            # Create main queue with DLQ
            response = sqs.create_queue(
                QueueName=queue_name,
                Attributes={
                    "VisibilityTimeout": "60",
                    "RedrivePolicy": f'{{"deadLetterTargetArn": "{dlq_arn}", "maxReceiveCount": "3"}}',
                },
            )
            queue_url = response["QueueUrl"]
            logger.info(f"Created queue '{queue_name}': {queue_url}")

        # Get DLQ URL
        try:
            dlq_response = sqs.get_queue_url(QueueName=dlq_name)
            dlq_url = dlq_response["QueueUrl"]
        except sqs.exceptions.QueueDoesNotExist:
            dlq_response = sqs.create_queue(
                QueueName=dlq_name,
                Attributes={
                    "VisibilityTimeout": "30",
                },
            )
            dlq_url = dlq_response["QueueUrl"]
            logger.info(f"Created DLQ '{dlq_name}': {dlq_url}")

        return queue_url, dlq_url

    except ClientError as e:
        logger.error(f"Failed to create SQS queues: {e}")
        raise


def main() -> int:
    """Main initialization function."""
    logger.info("Starting database initialization...")

    config = get_config()

    # Create DynamoDB client
    dynamodb = boto3.client(
        "dynamodb",
        endpoint_url=config["endpoint_url"],
        region_name=config["region_name"],
        aws_access_key_id=config["aws_access_key_id"],
        aws_secret_access_key=config["aws_secret_access_key"],
    )

    # Create SQS client
    sqs = boto3.client(
        "sqs",
        endpoint_url=config["endpoint_url"],
        region_name=config["region_name"],
        aws_access_key_id=config["aws_access_key_id"],
        aws_secret_access_key=config["aws_secret_access_key"],
    )

    # Create DynamoDB jobs table
    logger.info("Creating DynamoDB jobs table...")
    if not create_dynamodb_table(dynamodb, config["table_name"]):
        logger.error("Failed to create DynamoDB jobs table")
        return 1

    # Create DynamoDB idempotency keys table
    logger.info("Creating DynamoDB idempotency keys table...")
    if not create_idempotency_table(dynamodb, config["idempotency_table_name"]):
        logger.error("Failed to create DynamoDB idempotency table")
        return 1

    # Create SQS queues
    logger.info("Creating SQS queues...")
    try:
        queue_url, dlq_url = create_sqs_queue(
            sqs,
            config["queue_name"],
            config["dlq_name"],
        )
        logger.info(f"Main queue URL: {queue_url}")
        logger.info(f"DLQ URL: {dlq_url}")

        # Export URLs for use in the application
        print(f"\nExport these environment variables:")
        print(f"export SQS_QUEUE_URL={queue_url}")
        print(f"export SQS_DLQ_URL={dlq_url}")
        print(f"export DYNAMODB_TABLE_IDEMPOTENCY={config['idempotency_table_name']}")

    except Exception as e:
        logger.error(f"Failed to create SQS queues: {e}")
        return 1

    logger.info("Database initialization completed successfully!")
    return 0


if __name__ == "__main__":
    # Import for type hint
    from typing import Any

    sys.exit(main())
