#!/bin/bash
# Reto Prosperas - AWS Resources Initialization Script
# Creates SQS queues and DynamoDB tables for local development

set -e

echo "=============================================="
echo "Initializing AWS Resources in LocalStack..."
echo "=============================================="

# Configure AWS CLI to use LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Helper function to run awslocal commands
run_awslocal() {
    aws --endpoint-url=http://localhost:4566 "$@"
}

# Wait for LocalStack to be ready
echo "Waiting for LocalStack to be ready..."
until run_awslocal sqs list-queues &>/dev/null; do
    echo "LocalStack not ready yet, waiting..."
    sleep 2
done
echo "LocalStack is ready!"

# =============================================================================
# Create SQS Queues
# =============================================================================
echo ""
echo "Creating SQS Queues..."

# Main jobs queue with Dead Letter Queue configuration
echo "Creating main jobs queue..."
run_awslocal sqs create-queue \
    --queue-name report-jobs-queue \
    --attributes '{
        "VisibilityTimeout": "60",
        "MessageRetentionPeriod": "86400"
    }' 2>/dev/null || echo "Queue report-jobs-queue may already exist"

# Dead Letter Queue for failed messages
echo "Creating dead letter queue..."
run_awslocal sqs create-queue \
    --queue-name report-jobs-dlq \
    --attributes '{
        "VisibilityTimeout": "60",
        "MessageRetentionPeriod": "1209600"
    }' 2>/dev/null || echo "Queue report-jobs-dlq may already exist"

# Priority queue for high-priority jobs
echo "Creating priority queue..."
run_awslocal sqs create-queue \
    --queue-name report-jobs-priority \
    --attributes '{
        "VisibilityTimeout": "30",
        "MessageRetentionPeriod": "86400"
    }' 2>/dev/null || echo "Queue report-jobs-priority may already exist"

echo "SQS queues created successfully!"

# =============================================================================
# Create DynamoDB Tables
# =============================================================================
echo ""
echo "Creating DynamoDB Tables..."

# Jobs table with GSI on user_id for efficient user job queries
echo "Creating jobs table..."
run_awslocal dynamodb create-table \
    --table-name jobs \
    --attribute-definitions \
        AttributeName=job_id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
        AttributeName=created_at,AttributeType=S \
        AttributeName=status,AttributeType=S \
    --key-schema \
        AttributeName=job_id,KeyType=HASH \
    --global-secondary-indexes \
        "[
            {
                \"IndexName\": \"user_id-created_at-index\",
                \"KeySchema\": [
                    {\"AttributeName\": \"user_id\", \"KeyType\": \"HASH\"},
                    {\"AttributeName\": \"created_at\", \"KeyType\": \"RANGE\"}
                ],
                \"Projection\": {\"ProjectionType\": \"ALL\"},
                \"ProvisionedThroughput\": {\"ReadCapacityUnits\": 5, \"WriteCapacityUnits\": 5}
            },
            {
                \"IndexName\": \"status-created_at-index\",
                \"KeySchema\": [
                    {\"AttributeName\": \"status\", \"KeyType\": \"HASH\"},
                    {\"AttributeName\": \"created_at\", \"KeyType\": \"RANGE\"}
                ],
                \"Projection\": {\"ProjectionType\": \"ALL\"},
                \"ProvisionedThroughput\": {\"ReadCapacityUnits\": 5, \"WriteCapacityUnits\": 5}
            }
        ]" \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    2>/dev/null || echo "Table jobs may already exist"

# Enable TTL on jobs table for automatic cleanup
echo "Enabling TTL on jobs table..."
run_awslocal dynamodb update-time-to-live \
    --table-name jobs \
    --time-to-live-specification '{
        "Enabled": true,
        "AttributeName": "ttl"
    }' 2>/dev/null || echo "TTL configuration may have failed (optional)"

echo "DynamoDB tables created successfully!"

# =============================================================================
# Verify Resources
# =============================================================================
echo ""
echo "Verifying created resources..."

echo "SQS Queues:"
run_awslocal sqs list-queues

echo ""
echo "DynamoDB Tables:"
run_awslocal dynamodb list-tables

echo ""
echo "=============================================="
echo "AWS Resources initialized successfully!"
echo "=============================================="
echo ""
echo "Queue URLs (for reference):"
echo "  Main Queue:     http://localhost:4566/000000000000/report-jobs-queue"
echo "  Priority Queue: http://localhost:4566/000000000000/report-jobs-priority"
echo "  DLQ:            http://localhost:4566/000000000000/report-jobs-dlq"
echo ""
