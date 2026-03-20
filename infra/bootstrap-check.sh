#!/bin/bash
set -e

echo "=========================================="
echo "🔍 CDK Bootstrap Verification Script"
echo "=========================================="
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo "=========================================="

# Function to check if CDK is REALLY bootstrapped
check_cdk_really_bootstrapped() {
    echo "🔍 Checking if CDK is REALLY bootstrapped..."
    
    # Method 1: Check for S3 bootstrap bucket (MOST IMPORTANT)
    echo "Method 1: Checking S3 bootstrap bucket..."
    BOOTSTRAP_BUCKET="cdk-hnb659fds-assets-${AWS_ACCOUNT_ID}-${AWS_REGION}"
    
    if aws s3 ls "s3://${BOOTSTRAP_BUCKET}" 2>/dev/null; then
        echo "✅ CDK bootstrap bucket exists: ${BOOTSTRAP_BUCKET}"
        return 0
    else
        echo "❌ CDK bootstrap bucket does NOT exist: ${BOOTSTRAP_BUCKET}"
        return 1
    fi
}

# Function to check CloudFormation bootstrap stack
check_cfn_bootstrap_stack() {
    echo "Method 2: Checking CloudFormation bootstrap stack..."
    
    if aws cloudformation describe-stacks \
        --stack-name "CDKToolkit" \
        --region "${AWS_REGION}" \
        --query "Stacks[0].StackStatus" \
        --output text 2>/dev/null | grep -q "CREATE_COMPLETE\|UPDATE_COMPLETE"; then
        echo "✅ CDK bootstrap CloudFormation stack exists and is healthy"
        return 0
    else
        echo "❌ CDK bootstrap CloudFormation stack does NOT exist or is not healthy"
        return 1
    fi
}

# Function to bootstrap CDK
bootstrap_cdk() {
    echo "🚀 Bootstrapping CDK..."
    echo "Running: npx cdk bootstrap aws://${AWS_ACCOUNT_ID}/${AWS_REGION}"
    
    # Try bootstrap with retry logic
    local max_retries=3
    local retry_delay=10
    
    for attempt in $(seq 1 $max_retries); do
        echo "Attempt $attempt of $max_retries..."
        
        if npx cdk bootstrap aws://${AWS_ACCOUNT_ID}/${AWS_REGION} 2>&1; then
            echo "✅ CDK bootstrap command completed"
            
            # Verify bootstrap succeeded
            if check_cdk_really_bootstrapped; then
                echo "🎉 CDK bootstrap successful!"
                return 0
            else
                echo "⚠️ Bootstrap command succeeded but bucket verification failed"
            fi
        else
            echo "❌ CDK bootstrap attempt $attempt failed"
        fi
        
        if [ $attempt -lt $max_retries ]; then
            echo "⏳ Waiting $retry_delay seconds before retry..."
            sleep $retry_delay
        fi
    done
    
    echo "❌ All CDK bootstrap attempts failed"
    return 1
}

# Main execution
echo ""
echo "Starting CDK bootstrap verification..."

# Check if CDK is really bootstrapped
if check_cdk_really_bootstrapped; then
    echo "✅ CDK is REALLY bootstrapped (bucket exists)"
    exit 0
else
    echo "❌ CDK is NOT bootstrapped (bucket missing)"
    
    # Also check CloudFormation stack for more context
    check_cfn_bootstrap_stack || true
    
    echo ""
    echo "🔄 CDK needs to be bootstrapped..."
    
    if bootstrap_cdk; then
        echo "✅ CDK bootstrap completed successfully"
        exit 0
    else
        echo "❌ CDK bootstrap failed"
        echo ""
        echo "=========================================="
        echo "🛠️  TROUBLESHOOTING"
        echo "=========================================="
        echo "1. Check AWS credentials have AdministratorAccess"
        echo "2. Verify AWS account ID: ${AWS_ACCOUNT_ID}"
        echo "3. Verify AWS region: ${AWS_REGION}"
        echo "4. Check IAM permissions for:"
        echo "   - CloudFormation (full access)"
        echo "   - S3 (full access)"
        echo "   - IAM (full access)"
        echo "5. Manual bootstrap command:"
        echo "   npx cdk bootstrap aws://${AWS_ACCOUNT_ID}/${AWS_REGION}"
        echo "=========================================="
        exit 1
    fi
fi