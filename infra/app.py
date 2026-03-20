#!/usr/bin/env python3
"""
Reto Prosperas - CDK Application Entry Point

This module initializes the CDK application and defines the infrastructure stacks.
It orchestrates the deployment of:
- Data Stack: DynamoDB tables and SQS queues
- Compute Stack: App Runner services (API + Worker) with ECR
- API Stack: API Gateway with rate limiting
- CDN Stack: S3 static hosting + CloudFront

Usage:
    cdk --version
    cdk bootstrap aws://ACCOUNT/REGION
    cdk deploy --all
    cdk destroy --all
"""

import os
import sys
from pathlib import Path

import aws_cdk as cdk

# Add stacks directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from stacks.data_stack import DataStack
from stacks.compute_stack import ComputeStack
from stacks.api_stack import APIStack
from stacks.cdn_stack import CDNStack


def get_environment_context() -> cdk.Environment:
    """
    Get AWS environment from context or environment variables.

    Priority:
    1. CDK context (cdk.json or -c flag)
    2. Environment variables (CDK_ACCOUNT, CDK_REGION)
    3. Defaults for local development
    """
    app = cdk.App()

    # Use provided account or default to CDK_DEFAULT_ACCOUNT if available,
    # otherwise use placeholder for synthesis only
    account = os.environ.get(
        "CDK_ACCOUNT",
        os.environ.get("CDK_DEFAULT_ACCOUNT", "123456789012"),  # Default for synth
    )
    region = os.environ.get(
        "CDK_REGION", os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
    )

    return cdk.Environment(
        account=account,
        region=region,
    )


def synth_app() -> cdk.App:
    """
    Create and configure the CDK application.

    Returns:
        Configured CDK App instance with all stacks
    """
    app = cdk.App()

    # Environment configuration
    env = get_environment_context()

    # Stack naming prefix
    stack_prefix = app.node.try_get_context("stackPrefix") or "harrison"

    # =======================================================================
    # Data Stack: DynamoDB + SQS
    # =======================================================================
    data_stack = DataStack(
        app,
        f"{stack_prefix}-data-stack",
        stack_name=f"{stack_prefix}-data-stack",
        env=env,
        description="DynamoDB tables and SQS queues for job processing",
    )

    # =======================================================================
    # Compute Stack: App Runner + ECR
    # =======================================================================
    compute_stack = ComputeStack(
        app,
        f"{stack_prefix}-compute-stack",
        stack_name=f"{stack_prefix}-compute-stack",
        env=env,
        data_stack=data_stack,
        stack_prefix=stack_prefix,
        description="App Runner services (API + Worker) with ECR repositories",
    )

    # Add dependency: compute needs queue URLs from data stack
    compute_stack.add_dependency(data_stack)

    # =======================================================================
    # API Stack: API Gateway
    # =======================================================================
    api_stack = APIStack(
        app,
        f"{stack_prefix}-api-stack",
        stack_name=f"{stack_prefix}-api-stack",
        env=env,
        compute_stack=compute_stack,
        stack_prefix=stack_prefix,
        description="API Gateway with rate limiting for API access",
    )

    # Add dependency: API needs App Runner endpoint
    api_stack.add_dependency(compute_stack)

    # =======================================================================
    # CDN Stack: S3 + CloudFront
    # =======================================================================
    cdn_stack = CDNStack(
        app,
        f"{stack_prefix}-cdn-stack",
        stack_name=f"{stack_prefix}-cdn-stack",
        env=env,
        stack_prefix=stack_prefix,
        api_url=api_stack.api_url,
        description="S3 static hosting with CloudFront CDN for frontend",
    )

    # Output configuration
    cdk.Tags.of(app).add("Project", "RetoProsperas")
    cdk.Tags.of(app).add(
        "Environment", app.node.try_get_context("environment") or "production"
    )

    return app


if __name__ == "__main__":
    # Validate prerequisites
    if sys.version_info < (3, 9):
        print("Error: Python 3.9 or higher is required")
        sys.exit(1)

    # Create and synthesize the app
    app = synth_app()
    app.synth()
