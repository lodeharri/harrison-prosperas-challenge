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
    
    # Check bootstrap exit code
    BOOTSTRAP_EXIT_CODE=$?
    
    if [ $BOOTSTRAP_EXIT_CODE -eq 0 ]; then
        echo "✅ CDK bootstrap command completed successfully"
        
        # Try to verify bucket with retry logic (S3 eventual consistency)
        echo "Verifying bootstrap bucket (S3 eventual consistency)..."
        for i in {1..5}; do
            if aws s3 ls "s3://$BUCKET_NAME" 2>/dev/null; then
                echo "✅ CDK bootstrap bucket verified: $BUCKET_NAME"
                exit 0
            fi
            echo "Attempt $i: Bucket not yet visible, waiting 5 seconds..."
            sleep 5
        done
        
        # Even if bucket not visible, bootstrap might still be successful
        # (CDK bootstrap can succeed but bucket may take time to appear)
        echo "⚠️ Bootstrap bucket not immediately visible, but CDK bootstrap completed successfully"
        echo "Proceeding with deployment..."
        exit 0
    else
        echo "❌ CDK bootstrap command failed with exit code: $BOOTSTRAP_EXIT_CODE"
        exit 1
    fi
fi