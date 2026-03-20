"""
CDK Stacks Module

This module exports all infrastructure stacks for the Reto Prosperas project.
Each stack represents a logical grouping of AWS resources.

Stacks:
    - DataStack: DynamoDB tables and SQS queues
    - ComputeStack: App Runner services and ECR repositories
    - APIStack: API Gateway and rate limiting
    - CDNStack: S3 static hosting and CloudFront distribution
"""

from .data_stack import DataStack
from .compute_stack import ComputeStack
from .api_stack import APIStack
from .cdn_stack import CDNStack

__all__ = [
    "DataStack",
    "ComputeStack",
    "APIStack",
    "CDNStack",
]
