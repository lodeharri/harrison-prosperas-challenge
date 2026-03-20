#!/usr/bin/env python3
"""DynamoDB table and SQS queue initialization script.

This script initializes the required DynamoDB tables and SQS queues for the
report job processing system.

USAGE:
    LocalStack (development):
        python init_db.py
        (Creates tables and queues locally)

    AWS Production:
        python init_db.py
        (Verifies tables/queues exist, does NOT create them - CDK handles provisioning)

ENVIRONMENT VARIABLES:

    # AWS Configuration
    AWS_ENDPOINT_URL:     LocalStack endpoint (e.g., http://localhost:4566)
                         If NOT set → Use native AWS (production mode)
    AWS_REGION:          AWS region (default: us-east-1)
    AWS_ACCESS_KEY_ID:   AWS credentials (from CDK/IRSA in production)
    AWS_SECRET_ACCESS_KEY: AWS credentials (from CDK/IRSA in production)

    # DynamoDB Tables (AWS production names from CDK)
    DYNAMODB_TABLE_JOBS:       Table name (default: jobs, production: harrison-jobs)
    DYNAMODB_TABLE_IDEMPOTENCY: Table name (default: idempotency_keys)

    # SQS Queues (AWS production names from CDK)
    SQS_QUEUE_NAME:       Queue name (default: harrison-jobs-queue)
    SQS_DLQ_NAME:         DLQ name (default: harrison-jobs-dlq)
    SQS_PRIORITY_QUEUE_NAME: Priority queue name (default: harrison-jobs-priority)

AWS PRODUCTION RESOURCE NAMES:
    - Table: harrison-jobs
    - Table: harrison-idempotency
    - Queue: harrison-jobs-queue
    - DLQ: harrison-jobs-dlq
    - Priority Queue: harrison-jobs-priority
"""

import logging
import os
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _is_localstack() -> bool:
    """Check if running with LocalStack (development mode).

    Returns True if AWS_ENDPOINT_URL is defined, False for production AWS.
    """
    return os.getenv("AWS_ENDPOINT_URL") is not None


def get_config() -> dict:
    """Get configuration from environment variables.

    Resource names:
    - LocalStack: Uses default names (jobs, idempotency_keys, etc.)
    - Production: Uses CDK-defined names (harrison-jobs, harrison-idempotency, etc.)
    """
    is_local = _is_localstack()

    # Default names for LocalStack, production names from CDK env vars
    table_name = os.getenv(
        "DYNAMODB_TABLE_JOBS", "harrison-jobs" if not is_local else "jobs"
    )
    idempotency_table_name = os.getenv(
        "DYNAMODB_TABLE_IDEMPOTENCY",
        "harrison-idempotency" if not is_local else "idempotency_keys",
    )
    queue_name = os.getenv("SQS_QUEUE_NAME", "harrison-jobs-queue")
    dlq_name = os.getenv("SQS_DLQ_NAME", "harrison-jobs-dlq")
    priority_queue_name = os.getenv("SQS_PRIORITY_QUEUE_NAME", "harrison-jobs-priority")

    # Endpoint: LocalStack URL if set, None for native AWS
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")

    return {
        "endpoint_url": endpoint_url,
        "region_name": os.getenv("AWS_REGION", "us-east-1"),
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "table_name": table_name,
        "idempotency_table_name": idempotency_table_name,
        "queue_name": queue_name,
        "dlq_name": dlq_name,
        "priority_queue_name": priority_queue_name,
        "is_localstack": is_local,
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


def create_sqs_queue(
    sqs: Any, queue_name: str, dlq_name: str, priority_queue_name: str | None = None
) -> tuple[str, str, str | None]:
    """
    Create the SQS queues (main, DLQ, and optional priority queue).

    Args:
        sqs: Boto3 SQS client
        queue_name: Name for the main queue
        dlq_name: Name for the dead letter queue
        priority_queue_name: Optional name for priority queue

    Returns:
        Tuple of (queue_url, dlq_url, priority_queue_url | None)
    """
    priority_queue_url = None

    try:
        # Check if main queue already exists
        try:
            response = sqs.get_queue_url(QueueName=queue_name)
            queue_url = response["QueueUrl"]
            logger.info(f"Queue '{queue_name}' already exists: {queue_url}")
        except sqs.exceptions.QueueDoesNotExist:
            # Create DLQ first
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

        # Get/Create DLQ URL
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

        # Get/Create priority queue if specified
        if priority_queue_name:
            try:
                priority_response = sqs.get_queue_url(QueueName=priority_queue_name)
                priority_queue_url = priority_response["QueueUrl"]
                logger.info(
                    f"Priority queue '{priority_queue_name}' already exists: {priority_queue_url}"
                )
            except sqs.exceptions.QueueDoesNotExist:
                priority_response = sqs.create_queue(
                    QueueName=priority_queue_name,
                    Attributes={
                        "VisibilityTimeout": "60",
                    },
                )
                priority_queue_url = priority_response["QueueUrl"]
                logger.info(
                    f"Created priority queue '{priority_queue_name}': {priority_queue_url}"
                )

        return queue_url, dlq_url, priority_queue_url

    except ClientError as e:
        logger.error(f"Failed to create SQS queues: {e}")
        raise


def verify_aws_resources(config: dict, dynamodb: Any, sqs: Any) -> bool:
    """
    Verify that AWS resources exist (for production mode).

    In production, resources are created by CDK, so we just verify they exist.

    Args:
        config: Configuration dictionary
        dynamodb: Boto3 DynamoDB client
        sqs: Boto3 SQS client

    Returns:
        True if all resources exist
    """
    errors = []

    # Verify jobs table
    try:
        dynamodb.describe_table(TableName=config["table_name"])
        logger.info(f"✓ Jobs table exists: {config['table_name']}")
    except ClientError:
        errors.append(f"Jobs table not found: {config['table_name']}")

    # Verify idempotency table
    try:
        dynamodb.describe_table(TableName=config["idempotency_table_name"])
        logger.info(f"✓ Idempotency table exists: {config['idempotency_table_name']}")
    except ClientError:
        errors.append(
            f"Idempotency table not found: {config['idempotency_table_name']}"
        )

    # Verify main queue
    try:
        sqs.get_queue_url(QueueName=config["queue_name"])
        logger.info(f"✓ SQS queue exists: {config['queue_name']}")
    except ClientError:
        errors.append(f"SQS queue not found: {config['queue_name']}")

    # Verify DLQ
    try:
        sqs.get_queue_url(QueueName=config["dlq_name"])
        logger.info(f"✓ SQS DLQ exists: {config['dlq_name']}")
    except ClientError:
        errors.append(f"SQS DLQ not found: {config['dlq_name']}")

    # Verify priority queue
    try:
        sqs.get_queue_url(QueueName=config["priority_queue_name"])
        logger.info(f"✓ SQS priority queue exists: {config['priority_queue_name']}")
    except ClientError:
        errors.append(f"SQS priority queue not found: {config['priority_queue_name']}")

    if errors:
        logger.error("Production resource verification failed:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    logger.info("All AWS resources verified successfully!")
    return True


def main() -> int:
    """Main initialization function."""
    config = get_config()

    # Detect mode (LocalStack vs AWS Production)
    if config["is_localstack"]:
        logger.info("=" * 60)
        logger.info("MODE: LocalStack (Development)")
        logger.info("Will create tables and queues locally.")
        logger.info("=" * 60)
    else:
        logger.info("=" * 60)
        logger.info("MODE: AWS Production")
        logger.info("Will verify resources exist (CDK should have provisioned them).")
        logger.info("=" * 60)

    logger.info(f"Jobs Table: {config['table_name']}")
    logger.info(f"Idempotency Table: {config['idempotency_table_name']}")
    logger.info(f"Queue: {config['queue_name']}")
    logger.info(f"DLQ: {config['dlq_name']}")
    logger.info(f"Priority Queue: {config['priority_queue_name']}")

    # Create DynamoDB client
    dynamodb_kwargs = {
        "service_name": "dynamodb",
        "region_name": config["region_name"],
    }
    if config["endpoint_url"]:
        dynamodb_kwargs["endpoint_url"] = config["endpoint_url"]
    if config["aws_access_key_id"]:
        dynamodb_kwargs["aws_access_key_id"] = config["aws_access_key_id"]
    if config["aws_secret_access_key"]:
        dynamodb_kwargs["aws_secret_access_key"] = config["aws_secret_access_key"]

    dynamodb = boto3.client(**dynamodb_kwargs)

    # Create SQS client
    sqs_kwargs = {
        "service_name": "sqs",
        "region_name": config["region_name"],
    }
    if config["endpoint_url"]:
        sqs_kwargs["endpoint_url"] = config["endpoint_url"]
    if config["aws_access_key_id"]:
        sqs_kwargs["aws_access_key_id"] = config["aws_access_key_id"]
    if config["aws_secret_access_key"]:
        sqs_kwargs["aws_secret_access_key"] = config["aws_secret_access_key"]

    sqs = boto3.client(**sqs_kwargs)

    if config["is_localstack"]:
        # =================================================================
        # LOCALSTACK MODE: Create resources
        # =================================================================
        logger.info("Creating DynamoDB jobs table...")
        if not create_dynamodb_table(dynamodb, config["table_name"]):
            logger.error("Failed to create DynamoDB jobs table")
            return 1

        logger.info("Creating DynamoDB idempotency keys table...")
        if not create_idempotency_table(dynamodb, config["idempotency_table_name"]):
            logger.error("Failed to create DynamoDB idempotency table")
            return 1

        logger.info("Creating SQS queues...")
        try:
            queue_url, dlq_url, priority_queue_url = create_sqs_queue(
                sqs,
                config["queue_name"],
                config["dlq_name"],
                config["priority_queue_name"],
            )
            logger.info(f"Main queue URL: {queue_url}")
            logger.info(f"DLQ URL: {dlq_url}")
            if priority_queue_url:
                logger.info(f"Priority queue URL: {priority_queue_url}")

            # Export URLs for use in the application
            print(f"\n{'=' * 60}")
            print("Export these environment variables for LocalStack:")
            print(f"export SQS_QUEUE_URL={queue_url}")
            print(f"export SQS_DLQ_URL={dlq_url}")
            if priority_queue_url:
                print(f"export SQS_PRIORITY_QUEUE_URL={priority_queue_url}")
            print(f"export DYNAMODB_TABLE_JOBS={config['table_name']}")
            print(
                f"export DYNAMODB_TABLE_IDEMPOTENCY={config['idempotency_table_name']}"
            )
            print(f"export AWS_ENDPOINT_URL={config['endpoint_url']}")
            print(f"export AWS_REGION={config['region_name']}")
            print(f"export AWS_ACCESS_KEY_ID={config['aws_access_key_id'] or 'test'}")
            print(
                f"export AWS_SECRET_ACCESS_KEY={config['aws_secret_access_key'] or 'test'}"
            )
            print(f"{'=' * 60}\n")

        except Exception as e:
            logger.error(f"Failed to create SQS queues: {e}")
            return 1

        logger.info("LocalStack database initialization completed successfully!")

    else:
        # =================================================================
        # AWS PRODUCTION MODE: Verify resources
        # =================================================================
        logger.info("Verifying AWS resources...")
        if not verify_aws_resources(config, dynamodb, sqs):
            logger.error(
                "Resource verification failed. "
                "Ensure CDK has deployed the resources before running this script."
            )
            return 1

        logger.info("AWS resource verification completed successfully!")
        logger.info("\nEnvironment variables needed for production:")
        print(f"\n{'=' * 60}")
        print("Set these environment variables:")
        print(f"export DYNAMODB_TABLE_JOBS={config['table_name']}")
        print(f"export DYNAMODB_TABLE_IDEMPOTENCY={config['idempotency_table_name']}")
        print(f"export SQS_QUEUE_NAME={config['queue_name']}")
        print(f"export SQS_DLQ_NAME={config['dlq_name']}")
        print(f"export SQS_PRIORITY_QUEUE_NAME={config['priority_queue_name']}")
        print(f"export AWS_REGION={config['region_name']}")
        print(f"# (AWS credentials from IRSA/ECS task role)")
        print(f"{'=' * 60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
