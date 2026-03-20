#!/bin/bash
set -e

echo "Checking CDK bootstrap status..."

# Check if bootstrap bucket exists
BUCKET_NAME="cdk-hnb659fds-assets-${AWS_ACCOUNT_ID}-${AWS_REGION}"

if aws s3 ls "s3://$BUCKET_NAME" 2>/dev/null; then
    echo "✅ CDK bootstrap bucket exists: $BUCKET_NAME"
    exit 0
else
    echo "⚠️ CDK bootstrap bucket not found. Bootstrapping..."
    
    # Bootstrap CDK
    npx cdk bootstrap aws://${AWS_ACCOUNT_ID}/${AWS_REGION} \
      --cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess
    
    # Verify bootstrap
    if aws s3 ls "s3://$BUCKET_NAME" 2>/dev/null; then
        echo "✅ CDK bootstrap successful"
        exit 0
    else
        echo "❌ CDK bootstrap failed"
        exit 1
    fi
fi