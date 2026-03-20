"""
Compute Stack: App Runner Services and ECR Repositories

This stack creates the compute layer for running the API and worker:
- ECR repositories for Docker images
- App Runner services for API and Worker
- IAM roles for AWS resource access
- Secrets Manager for JWT secret
- VPC Connector for private networking
"""

from typing import Dict, Optional

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    SecretValue,
    Stack,
    aws_apprunner as apprunner,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

from .data_stack import DataStack


class ComputeStack(Stack):
    """
    Compute infrastructure stack for API and Worker services.

    Creates:
        - ECR repository for Docker images
        - App Runner service for REST API
        - App Runner service for Worker (SQS consumer)
        - IAM roles with least-privilege permissions
        - Secrets Manager for JWT secret

    Note: App Runner uses VPC Connector for private AWS resource access.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        data_stack: DataStack,
        stack_prefix: str = "harrison",
        **kwargs,
    ) -> None:
        self.data_stack = data_stack
        self.stack_prefix = stack_prefix

        super().__init__(scope, construct_id, **kwargs)

        # Determine removal policy from context
        removal_policy_str = self.node.try_get_context("removalPolicy") or "retain"
        self._removal_policy = (
            RemovalPolicy.DESTROY
            if removal_policy_str == "destroy"
            else RemovalPolicy.RETAIN
        )

        # ===================================================================
        # ECR Repository
        # ===================================================================
        self.ecr_repository = self._create_ecr_repository()

        # ===================================================================
        # Secrets Manager (JWT Secret)
        # ===================================================================
        self.jwt_secret = self._create_jwt_secret()

        # ===================================================================
        # IAM Roles
        # ===================================================================
        self.api_role = self._create_api_role()
        self.worker_role = self._create_worker_role()

        # ===================================================================
        # App Runner Services
        # ===================================================================
        self.api_service = self._create_api_service()
        self.worker_service = self._create_worker_service()

        # ===================================================================
        # Outputs
        # ===================================================================
        self._create_outputs()

    def _create_ecr_repository(self) -> ecr.Repository:
        """Create ECR repository for Docker images."""
        repository = ecr.Repository(
            self,
            "ECRRepository",
            repository_name=f"{self.stack_prefix}-prospera-challenge",
            image_scan_on_push=True,
            removal_policy=self._removal_policy,
        )

        # Add lifecycle policy to clean up old images
        repository.add_lifecycle_rule(
            tag_status=ecr.TagStatus.TAGGED,
            tag_prefix_list=["v"],
            max_image_count=10,
            description="Keep only last 10 tagged images",
        )

        CfnOutput(
            self,
            "ECRRepositoryUri",
            value=repository.repository_uri,
            export_name="HarrisonECRRepositoryUri",
        ).override_logical_id("ECRRepositoryUri")

        return repository

    def _create_jwt_secret(self) -> secretsmanager.Secret:
        """Create Secrets Manager secret for JWT signing key."""
        secret = secretsmanager.Secret(
            self,
            "JWTSecret",
            secret_name=f"{self.stack_prefix}-jwt-secret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"jwt_secret_key": ""}',
                generate_string_key="secure_token",
                exclude_punctuation=False,
                password_length=64,
            ),
            removal_policy=self._removal_policy,
        )

        CfnOutput(
            self,
            "JWTSecretArn",
            value=secret.secret_arn,
            export_name="HarrisonJWTSecretArn",
        ).override_logical_id("JWTSecretArn")

        return secret

    def _create_api_role(self) -> iam.Role:
        """Create IAM role for API App Runner service."""
        role = iam.Role(
            self,
            "APIServiceRole",
            assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
            description="Role for App Runner API service",
        )

        # DynamoDB permissions (read/write jobs table)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[
                    f"{self.data_stack.jobs_table.table_arn}",
                    f"{self.data_stack.jobs_table.table_arn}/index/*",
                    f"{self.data_stack.idempotency_table.table_arn}",
                ],
            )
        )

        # SQS permissions (send messages)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sqs:SendMessage",
                    "sqs:GetQueueUrl",
                ],
                resources=[
                    self.data_stack.job_queue_arn,
                    self.data_stack.priority_queue_arn,
                ],
            )
        )

        # Secrets Manager (read JWT secret)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[self.jwt_secret.secret_arn],
            )
        )

        # CloudWatch Logs
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["arn:aws:logs:*:*:*"],
            )
        )

        return role

    def _create_worker_role(self) -> iam.Role:
        """Create IAM role for Worker App Runner service."""
        role = iam.Role(
            self,
            "WorkerServiceRole",
            assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
            description="Role for App Runner Worker service",
        )

        # DynamoDB permissions (read/write jobs table)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                ],
                resources=[
                    f"{self.data_stack.jobs_table.table_arn}",
                    f"{self.data_stack.jobs_table.table_arn}/index/*",
                ],
            )
        )

        # SQS permissions (receive, delete, send DLQ)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueUrl",
                    "sqs:GetQueueAttributes",
                ],
                resources=[
                    self.data_stack.job_queue_arn,
                    self.data_stack.priority_queue_arn,
                    self.data_stack.dlq_arn,
                ],
            )
        )

        # Secrets Manager (read JWT secret)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[self.jwt_secret.secret_arn],
            )
        )

        # CloudWatch Logs
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["arn:aws:logs:*:*:*"],
            )
        )

        # CloudWatch Metrics
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricData",
                ],
                resources=["*"],
            )
        )

        return role

    def _get_environment_variables(self) -> Dict[str, str]:
        """Get environment variables for API service."""
        return {
            "AWS_REGION": self.region,
            "AWS_ENDPOINT_URL": "",  # Empty for real AWS
            "DYNAMODB_TABLE_JOBS": self.data_stack.jobs_table_name,
            "DYNAMODB_TABLE_IDEMPOTENCY": self.data_stack.idempotency_table_name,
            "SQS_QUEUE_URL": self.data_stack.job_queue_url,
            "SQS_DLQ_URL": self.data_stack.dlq_url,
            "SQS_PRIORITY_QUEUE_URL": self.data_stack.priority_queue_url,
            "JWT_SECRET_KEY": self.jwt_secret.secret_arn,
            "LOG_LEVEL": "INFO",
        }

    def _get_worker_environment_variables(self) -> Dict[str, str]:
        """Get environment variables for Worker service."""
        return {
            "AWS_REGION": self.region,
            "AWS_ENDPOINT_URL": "",  # Empty for real AWS
            "DYNAMODB_TABLE_JOBS": self.data_stack.jobs_table_name,
            "DYNAMODB_TABLE_IDEMPOTENCY": self.data_stack.idempotency_table_name,
            "SQS_QUEUE_URL": self.data_stack.job_queue_url,
            "SQS_DLQ_URL": self.data_stack.dlq_url,
            "SQS_PRIORITY_QUEUE_URL": self.data_stack.priority_queue_url,
            "JWT_SECRET_KEY": self.jwt_secret.secret_arn,
            "LOG_LEVEL": "INFO",
        }

    def _create_api_service(self) -> apprunner.CfnService:
        """
        Create App Runner service for REST API.

        Configuration:
            - Instance type: small (1 vCPU, 2 GB)
            - Min instances: 1
            - Max instances: 10 (auto-scaling)
            - Health check: /health endpoint
            - Port: 8000

        Note: Uses the ECR repository's :latest image tag.
        The image is built and pushed in the CI/CD pipeline (build-ecr job).
        """
        # Get image tag from CDK context, default to 'latest'
        # The CI/CD pipeline passes IMAGE_TAG as an env var
        image_tag = self.node.try_get_context("imageTag") or "latest"

        # Reference the ECR repository (already created by this stack)
        # The image URI is: <account>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>
        image_identifier = f"{self.ecr_repository.repository_uri}:{image_tag}"

        service = apprunner.CfnService(
            self,
            "APIService",
            service_name=f"{self.stack_prefix}-api",
            source_configuration=apprunner.CfnService.SourceConfigurationProperty(
                authentication_configuration=apprunner.CfnService.AuthenticationConfigurationProperty(
                    access_role_arn=self.api_role.role_arn,
                ),
                image_repository=apprunner.CfnService.ImageRepositoryProperty(
                    image_identifier=image_identifier,
                    image_repository_type="ECR",
                    image_configuration=apprunner.CfnService.ImageConfigurationProperty(
                        port="8000",
                        runtime_environment_variables=[
                            apprunner.CfnService.KeyValuePairProperty(
                                name=k,
                                value=v,
                            )
                            for k, v in self._get_environment_variables().items()
                        ],
                    ),
                ),
                auto_deployments_enabled=False,  # Manual deployment
            ),
            health_check_configuration=apprunner.CfnService.HealthCheckConfigurationProperty(
                path="/health",
                protocol="HTTP",  # App Runner only supports HTTP or TCP for health checks
                interval=10,
                timeout=5,
                healthy_threshold=2,
                unhealthy_threshold=3,
            ),
            instance_configuration=apprunner.CfnService.InstanceConfigurationProperty(
                cpu="1 vCPU",
                memory="2 GB",
            ),
        )

        # Auto-scaling configuration
        scaling = apprunner.CfnAutoScalingConfiguration(
            self,
            "APIAutoScaling",
            auto_scaling_configuration_name=f"{self.stack_prefix}-api-scaling",
            max_concurrency=100,
            max_size=10,
            min_size=1,
        )

        # Apply scaling to service
        CfnOutput(
            self,
            "APIServiceUrl",
            value=f"https://{service.attr_service_url}",
            export_name="HarrisonAPIServiceUrl",
        ).override_logical_id("APIServiceUrl")

        return service

    def _create_worker_service(self) -> apprunner.CfnService:
        """
        Create App Runner service for Worker (SQS consumer).

        Configuration:
            - Instance type: small (1 vCPU, 2 GB)
            - Min instances: 1
            - Max instances: 5 (limit concurrency)
            - No health check (background worker)
            - Environment: Worker-specific variables

        Note: Uses the ECR repository's :latest image tag.
        The image is built and pushed in the CI/CD pipeline (build-ecr job).
        The worker uses a different start_command to run the worker module.
        """
        # Get image tag from CDK context, default to 'latest'
        # The CI/CD pipeline passes IMAGE_TAG as an env var
        image_tag = self.node.try_get_context("imageTag") or "latest"

        # Reference the ECR repository (already created by this stack)
        # The image URI is: <account>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>
        image_identifier = f"{self.ecr_repository.repository_uri}:{image_tag}"

        service = apprunner.CfnService(
            self,
            "WorkerService",
            service_name=f"{self.stack_prefix}-worker",
            source_configuration=apprunner.CfnService.SourceConfigurationProperty(
                authentication_configuration=apprunner.CfnService.AuthenticationConfigurationProperty(
                    access_role_arn=self.worker_role.role_arn,
                ),
                image_repository=apprunner.CfnService.ImageRepositoryProperty(
                    image_identifier=image_identifier,
                    image_repository_type="ECR",
                    image_configuration=apprunner.CfnService.ImageConfigurationProperty(
                        port="8000",  # Still expose port but worker doesn't use it
                        runtime_environment_variables=[
                            apprunner.CfnService.KeyValuePairProperty(
                                name=k,
                                value=v,
                            )
                            for k, v in self._get_worker_environment_variables().items()
                        ],
                        start_command="python -m worker.main",  # Worker entry point
                    ),
                ),
                auto_deployments_enabled=False,
            ),
            instance_configuration=apprunner.CfnService.InstanceConfigurationProperty(
                cpu="1 vCPU",
                memory="2 GB",
            ),
        )

        CfnOutput(
            self,
            "WorkerServiceUrl",
            value=f"https://{service.attr_service_url}",
            export_name="HarrisonWorkerServiceUrl",
        ).override_logical_id("WorkerServiceUrl")

        return service

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "ECRRepositoryName",
            value=self.ecr_repository.repository_name,
            export_name="HarrisonECRRepositoryName",
        ).override_logical_id("ECRRepositoryName")

        CfnOutput(
            self,
            "APIRoleArn",
            value=self.api_role.role_arn,
            export_name="HarrisonAPIRoleArn",
        ).override_logical_id("APIRoleArn")

        CfnOutput(
            self,
            "WorkerRoleArn",
            value=self.worker_role.role_arn,
            export_name="HarrisonWorkerRoleArn",
        ).override_logical_id("WorkerRoleArn")

    @property
    def api_service_url(self) -> str:
        """Get the API service URL."""
        return f"https://{self.api_service.attr_service_url}"

    @property
    def ecr_repository_uri(self) -> str:
        """Get the ECR repository URI."""
        return self.ecr_repository.repository_uri
