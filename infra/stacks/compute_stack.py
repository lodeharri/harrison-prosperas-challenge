"""
Compute Stack: ECS Fargate Services and ECR Repositories

This stack creates the compute layer for running the API and worker:
- ECR repositories for Docker images
- ECS Fargate services for API and Worker
- IAM roles for AWS resource access
- Secrets Manager for JWT secret
"""

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_elasticloadbalancingv2 as elbv2,
    aws_applicationautoscaling as appscaling,
    aws_cloudwatch as cloudwatch,
)
from constructs import Construct

from .data_stack import DataStack


class ComputeStack(Stack):
    """
    Compute infrastructure stack for API and Worker services.

    Creates:
        - ECR repository for Docker images
        - ECS Fargate service for REST API
        - ECS Fargate service for Worker (SQS consumer)
        - IAM roles with least-privilege permissions
        - Secrets Manager for JWT secret

    Note: Uses ECS Fargate for both API and Worker for consistency.
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
        # ECS Fargate Services
        # ===================================================================
        self.api_service = self._create_api_service()
        self.worker_service = self._create_worker_service()

        # ===================================================================
        # Outputs
        # ===================================================================
        self._create_outputs()

    def _create_ecr_repository(self) -> ecr.Repository:
        """Get or create ECR repository for Docker images."""
        repo_name = f"{self.stack_prefix}-prospera-challenge"

        # Try to import existing repository (for idempotency)
        try:
            repository = ecr.Repository.from_repository_name(
                self,
                "ECRRepository",
                repository_name=repo_name,
            )
            # Output for existing repository
            CfnOutput(
                self,
                "ECRRepositoryUri",
                value=repository.repository_uri,
                export_name="HarrisonECRRepositoryUri",
            ).override_logical_id("ECRRepositoryUri")
            return repository
        except Exception:
            # Repository doesn't exist, create it
            pass

        # Create new repository
        repository = ecr.Repository(
            self,
            "ECRRepository",
            repository_name=repo_name,
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
        """Get or create Secrets Manager secret for JWT signing key."""
        secret_name = f"{self.stack_prefix}-jwt-secret"

        # Try to import existing secret (for idempotency)
        try:
            existing = secretsmanager.Secret.from_secret_name_v2(
                self,
                "JWTSecret",
                secret_name=secret_name,
            )
            # Verify it has the arn property
            if hasattr(existing, "secret_arn") and existing.secret_arn:
                # Output for existing secret
                CfnOutput(
                    self,
                    "JWTSecretArn",
                    value=existing.secret_arn,
                    export_name="HarrisonJWTSecretArn",
                ).override_logical_id("JWTSecretArn")
                return existing
        except Exception:
            pass

        # Secret doesn't exist, create it
        secret = secretsmanager.Secret(
            self,
            "JWTSecret",
            secret_name=secret_name,
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
        """Create IAM role for API ECS Fargate task."""
        role = iam.Role(
            self,
            "APIServiceRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="Role for ECS Fargate API task",
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
                    "dynamodb:DescribeTable",
                ],
                resources=[
                    self.data_stack.jobs_table.table_arn,
                    f"{self.data_stack.jobs_table.table_arn}/index/*",
                    self.data_stack.idempotency_table.table_arn,
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
                    "sqs:GetQueueAttributes",
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
        """Create IAM role for Worker ECS Fargate task."""
        role = iam.Role(
            self,
            "WorkerServiceRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="Role for ECS Worker task",
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
                    self.data_stack.jobs_table.table_arn,
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

        # Application Auto Scaling permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "application-autoscaling:RegisterScalableTarget",
                    "application-autoscaling:DescribeScalableTargets",
                    "application-autoscaling:PutScalingPolicy",
                    "application-autoscaling:DescribeScalingPolicies",
                    "cloudwatch:PutMetricAlarm",
                    "cloudwatch:DeleteAlarms",
                    "cloudwatch:DescribeAlarms",
                ],
                resources=["*"],
            )
        )

        return role

    def _create_api_service(self) -> ecs_patterns.ApplicationLoadBalancedFargateService:
        """
        Create ECS Fargate service with Application Load Balancer for REST API.

        Configuration:
            - CPU: 512 (0.5 vCPU)
            - Memory: 1024 MB (1 GB)
            - Desired count: 1
            - Health check: HTTP /health on port 8000
            - ALB provides stable public URL for API Gateway integration

        Note: Uses ApplicationLoadBalancedFargateService which automatically
        creates an ALB with a stable DNS name.
        """
        # Get image tag from CDK context
        image_tag = self.node.try_get_context("imageTag") or "latest"

        # Create the load balanced Fargate service
        load_balanced_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "APIService",
            service_name=f"{self.stack_prefix}-api",
            cluster=self.data_stack.ecs_cluster,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(
                    repository=self.ecr_repository,
                    tag=image_tag,
                ),
                container_name="api",
                container_port=8000,
                task_role=self.api_role,
                environment={
                    "AWS_REGION": self.region,
                    "DYNAMODB_TABLE_JOBS": self.data_stack.jobs_table_name,
                    "DYNAMODB_TABLE_IDEMPOTENCY": self.data_stack.idempotency_table_name,
                    "SQS_QUEUE_URL": self.data_stack.job_queue_url,
                    "SQS_QUEUE_NAME": self.data_stack.job_queue_name,
                    "SQS_DLQ_URL": self.data_stack.dlq_url,
                    "SQS_DLQ_NAME": self.data_stack.dlq_name,
                    "SQS_PRIORITY_QUEUE_URL": self.data_stack.priority_queue_url,
                    "SQS_PRIORITY_QUEUE_NAME": self.data_stack.priority_queue_name,
                    "LOG_LEVEL": "INFO",
                },
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix=f"{self.stack_prefix}/api"
                ),
            ),
            assign_public_ip=True,
            desired_count=1,
            min_healthy_percent=50,
            max_healthy_percent=200,
            public_load_balancer=True,
            health_check_grace_period=cdk.Duration.seconds(30),
        )

        # Add target health check configuration
        load_balanced_service.target_group.configure_health_check(
            path="/health",
            port="8000",
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
            timeout=cdk.Duration.seconds(5),
            interval=cdk.Duration.seconds(10),
        )

        # Allow external access on port 8000 for WebSocket connections
        # This is needed because API Gateway doesn't support WebSocket,
        # so frontend connects directly to ALB for real-time notifications
        alb_sg = load_balanced_service.load_balancer.connections.security_groups[0]
        from aws_cdk import aws_ec2 as ec2

        alb_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(8000),
            description="Allow WebSocket connections from internet",
        )

        # Add listener on port 8000 for WebSocket connections
        # The default listener is on port 80, but FastAPI listens on 8000
        # Create a new listener for port 8000
        elbv2.ApplicationListener(
            self,
            "WebSocketListener",
            load_balancer=load_balanced_service.load_balancer,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_action=elbv2.ListenerAction.forward(
                [load_balanced_service.target_group]
            ),
        )

        # Output the ALB DNS name (stable URL for API Gateway)
        CfnOutput(
            self,
            "APIServiceUrl",
            value=f"http://{load_balanced_service.load_balancer.load_balancer_dns_name}:8000",
            export_name="HarrisonAPIServiceUrl",
        ).override_logical_id("APIServiceUrl")

        # Output the security group for reference
        CfnOutput(
            self,
            "APIServiceSecurityGroup",
            value=load_balanced_service.service.connections.security_groups[
                0
            ].security_group_id,
            export_name="HarrisonAPIServiceSecurityGroup",
        ).override_logical_id("APIServiceSecurityGroup")

        # Return the load balanced service wrapper (contains the FargateService)
        return load_balanced_service

    def _create_worker_service(self) -> ecs.FargateService:
        """
        Create ECS Fargate service for Worker (SQS consumer with WebSocket).

        Configuration:
            - CPU: 256 (0.25 vCPU)
            - Memory: 512 MB
            - Desired count: 1 (can scale)
            - No health check (background worker)
            - Environment: Worker-specific variables

        Note: Uses ECS Fargate because the worker maintains WebSocket
        connections and needs persistent connections to SQS.
        """
        # Get image tag from CDK context, default to 'latest'
        image_tag = self.node.try_get_context("imageTag") or "latest"

        # Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "WorkerTaskDefinition",
            cpu=256,
            memory_limit_mib=512,
            task_role=self.worker_role,
        )

        # Add container with worker command
        task_definition.add_container(
            "WorkerContainer",
            image=ecs.ContainerImage.from_ecr_repository(
                repository=self.ecr_repository,
                tag=image_tag,
            ),
            environment={
                "AWS_REGION": self.region,
                "DYNAMODB_TABLE_JOBS": self.data_stack.jobs_table_name,
                "DYNAMODB_TABLE_IDEMPOTENCY": self.data_stack.idempotency_table_name,
                "SQS_QUEUE_URL": self.data_stack.job_queue_url,
                "SQS_QUEUE_NAME": self.data_stack.job_queue_name,
                "SQS_DLQ_URL": self.data_stack.dlq_url,
                "SQS_DLQ_NAME": self.data_stack.dlq_name,
                "SQS_PRIORITY_QUEUE_URL": self.data_stack.priority_queue_url,
                "SQS_PRIORITY_QUEUE_NAME": self.data_stack.priority_queue_name,
                "LOG_LEVEL": "INFO",
                # Worker calls API's /internal/notify endpoint for WebSocket notifications
                "API_BASE_URL": f"http://{self.api_service.load_balancer.load_balancer_dns_name}:8000",
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix=f"{self.stack_prefix}/worker"
            ),
            command=["python", "-m", "backend.worker.main"],
        )

        # ECS Service (Fargate)
        service = ecs.FargateService(
            self,
            "WorkerService",
            cluster=self.data_stack.ecs_cluster,
            task_definition=task_definition,
            assign_public_ip=True,
            desired_count=1,
            min_healthy_percent=50,
            max_healthy_percent=200,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # ===================================================================
        # Application Auto Scaling for Worker
        # ===================================================================
        self._create_worker_autoscaling(service)

        CfnOutput(
            self,
            "WorkerServiceName",
            value=service.service_name,
            export_name="HarrisonWorkerServiceName",
        ).override_logical_id("WorkerServiceName")

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
    def ecr_repository_uri(self) -> str:
        """Get the ECR repository URI."""
        return self.ecr_repository.repository_uri

    @property
    def api_service_url(self) -> str:
        """Get the API service URL (ALB DNS name)."""
        # Get from the load balancer output
        return f"http://{self.api_service.load_balancer.load_balancer_dns_name}"

    @property
    def load_balancer_dns_name(self) -> str:
        """Get the API service URL (ALB DNS name)."""
        # Get from the load balancer output
        return self.api_service.load_balancer.load_balancer_dns_name

    def _create_worker_autoscaling(self, service: ecs.FargateService) -> None:
        """
        Configure Application Auto Scaling for Worker service based on SQS queue depth.

        Configuration:
            - Min Capacity: 1
            - Max Capacity: 8
            - Target: 75 messages per task (ApproximateNumberOfMessagesVisible / RunningTasks)
            - Scale-out cooldown: 60 seconds
            - Scale-in cooldown: 300 seconds

        Uses a target tracking scaling policy that scales based on the SQS queue
        message count divided by the number of running tasks.
        """
        # Create IAM role for autoscaling
        auto_scaling_role = iam.Role(
            self,
            "WorkerAutoScalingRole",
            assumed_by=iam.ServicePrincipal("application-autoscaling.amazonaws.com"),
            description="Role for ECS Service Auto Scaling",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonECS_FullAccess"),
            ],
        )

        # Create Scalable Target for ECS Service
        scalable_target = appscaling.ScalableTarget(
            self,
            "WorkerScalableTarget",
            service_namespace=appscaling.ServiceNamespace.ECS,
            scalable_dimension="ecs:service:DesiredCount",
            max_capacity=8,
            min_capacity=1,
            resource_id=f"service/{self.data_stack.ecs_cluster.cluster_name}/{service.service_name}",
            role=auto_scaling_role,
        )

        # Create target tracking scaling policy based on SQS queue depth
        # Target: 25 messages per task for optimal processing throughput
        scalable_target.scale_to_track_metric(
            "WorkerTargetTrackingPolicy",
            target_value=25.0,
            custom_metric=cloudwatch.Metric(
                namespace="AWS/SQS",
                metric_name="ApproximateNumberOfMessagesVisible",
                dimensions_map={
                    "QueueName": self.data_stack.job_queue_name,
                },
                statistic="Average",
                period=Duration.minutes(1),
            ),
            # Disable scale-in to use step scaling for more control
            disable_scale_in=False,
        )
