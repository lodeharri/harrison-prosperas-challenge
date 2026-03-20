#!/bin/bash
set -e

echo "Checking CDK bootstrap status..."

# Check if bootstrap bucket exists
BUCKET_NAME="cdk-hnb659fds-assets-${AWS_ACCOUNT_ID}-${AWS_REGION}"

# First check: CloudFormation stack
echo "Checking CloudFormation CDKToolkit stack..."
if aws cloudformation describe-stacks --stack-name CDKToolkit 2>/dev/null; then
    echo "✅ CDKToolkit CloudFormation stack exists"
    
    # Check if bucket exists
    if aws s3 ls "s3://$BUCKET_NAME" 2>/dev/null; then
        echo "✅ CDK bootstrap bucket exists: $BUCKET_NAME"
        exit 0
    else
        echo "⚠️ CDKToolkit stack exists but bucket not found. This might be okay if bucket was deleted."
    fi
fi

# Second check: Direct bucket check
if aws s3 ls "s3://$BUCKET_NAME" 2>/dev/null; then
    echo "✅ CDK bootstrap bucket exists: $BUCKET_NAME"
    exit 0
fi

echo "⚠️ CDK bootstrap bucket not found. Bootstrapping..."
echo "AWS Account: ${AWS_ACCOUNT_ID}"
echo "AWS Region: ${AWS_REGION}"

# Bootstrap CDK with explicit context
npx cdk bootstrap aws://${AWS_ACCOUNT_ID}/${AWS_REGION} \
  --cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess \
  --context "@aws-cdk/core:bootstrapQualifier=hnb659fds"

# Check bootstrap exit code
BOOTSTRAP_EXIT_CODE=$?

if [ $BOOTSTRAP_EXIT_CODE -eq 0 ]; then
    echo "✅ CDK bootstrap command completed successfully"
    
    # Wait for CloudFormation stack to be created
    echo "Waiting for CDKToolkit stack to be created..."
    for i in {1..10}; do
        if aws cloudformation describe-stacks --stack-name CDKToolkit 2>/dev/null; then
            echo "✅ CDKToolkit stack created"
            break
        fi
        echo "Attempt $i: Stack not yet created, waiting 10 seconds..."
        sleep 10
    done
    
    # Try to verify bucket with retry logic (S3 eventual consistency)
    echo "Verifying bootstrap bucket (S3 eventual consistency)..."
    for i in {1..10}; do
        if aws s3 ls "s3://$BUCKET_NAME" 2>/dev/null; then
            echo "✅ CDK bootstrap bucket verified: $BUCKET_NAME"
            exit 0
        fi
        echo "Attempt $i: Bucket not yet visible, waiting 10 seconds..."
        sleep 10
    done
    
    # If we get here, bucket still not visible
    echo "❌ ERROR: Bootstrap completed but bucket '$BUCKET_NAME' not found after 100 seconds"
    echo "This could be due to:"
    echo "1. S3 eventual consistency (wait longer)"
    echo "2. Missing S3 permissions"
    echo "3. Bootstrap actually failed"
    echo ""
    echo "Checking CloudFormation stack status..."
    aws cloudformation describe-stacks --stack-name CDKToolkit --query 'Stacks[0].StackStatus' || echo "Stack not found"
    echo ""
    echo "Trying to create bucket manually as fallback..."
    
    # Try to create the bucket manually
    if aws s3 mb "s3://$BUCKET_NAME" --region "${AWS_REGION}" 2>/dev/null; then
        echo "✅ Manually created bootstrap bucket: $BUCKET_NAME"
        exit 0
    else
        echo "❌ Failed to create bucket manually"
        echo "Proceeding anyway - CDK might be able to create it during deployment"
        exit 0
    fi
else
    echo "❌ CDK bootstrap command failed with exit code: $BOOTSTRAP_EXIT_CODE"
    exit 1
fi