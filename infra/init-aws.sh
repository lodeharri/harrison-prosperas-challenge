#!/bin/bash
# AWS Resource Initialization Script for LocalStack
# This script runs when LocalStack is ready

set -e

echo "=============================================="
echo "Initializing AWS Resources in LocalStack..."
echo "=============================================="

# Wait for LocalStack to be fully ready
echo "Waiting for LocalStack to be ready..."
sleep 10
echo "LocalStack is ready!"

# Create SQS Queues
echo ""
echo "Creating SQS Queues..."
echo "Creating main jobs queue..."
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name report-jobs-queue
echo "Creating dead letter queue..."
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name report-jobs-dlq
echo "Creating priority queue..."
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name report-jobs-priority
echo "SQS queues created successfully!"

# Create DynamoDB Tables
echo ""
echo "Creating DynamoDB Tables..."
echo "Creating jobs table..."
aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name jobs \
    --attribute-definitions \
        AttributeName=job_id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
        AttributeName=created_at,AttributeType=S \
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
                \"Projection\": {
                    \"ProjectionType\": \"ALL\"
                },
                \"ProvisionedThroughput\": {
                    \"ReadCapacityUnits\": 5,
                    \"WriteCapacityUnits\": 5
                }
            }
        ]" \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5

# Enable TTL for jobs table
echo "Enabling TTL on jobs table..."
aws --endpoint-url=http://localhost:4566 dynamodb update-time-to-live \
    --table-name jobs \
    --time-to-live-specification "Enabled=true,AttributeName=ttl"

echo "Creating idempotency_keys table..."
aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name idempotency_keys \
    --attribute-definitions \
        AttributeName=idempotency_key,AttributeType=S \
    --key-schema \
        AttributeName=idempotency_key,KeyType=HASH \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5

echo "DynamoDB tables created successfully!"

# Create S3 bucket for frontend
echo ""
echo "Creating S3 bucket for frontend..."
aws --endpoint-url=http://localhost:4566 s3 mb s3://harrison-frontend-bucket || echo "Bucket may already exist"

echo ""
echo "Verifying created resources..."
echo "SQS Queues:"
aws --endpoint-url=http://localhost:4566 sqs list-queues
echo ""
echo "DynamoDB Tables:"
aws --endpoint-url=http://localhost:4566 dynamodb list-tables

echo ""
echo "=============================================="
echo "AWS Resources initialized successfully!"
echo "=============================================="
echo ""
echo "Queue URLs (for reference):"
echo "  Main Queue:     http://localhost:4566/000000000000/report-jobs-queue"
echo "  Priority Queue: http://localhost:4566/000000000000/report-jobs-priority"
echo "  DLQ:            http://localhost:4566/000000000000/report-jobs-dlq"