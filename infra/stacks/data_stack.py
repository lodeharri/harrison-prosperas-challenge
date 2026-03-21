"""
Data Stack: DynamoDB Tables and SQS Queues

This stack creates the foundational data layer for the job processing system:
- Jobs table with GSI for user queries
- Idempotency keys table with TTL
- Main job queue with DLQ support
- Priority queue for high-priority jobs
"""

from typing import Dict, Optional

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_dynamodb as dynamodb,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_sqs as sqs,
)
from constructs import Construct


class DataStack(Stack):
    """
    Data infrastructure stack for job processing.

    Creates:
        - DynamoDB tables for job persistence and idempotency
        - SQS queues for job processing with DLQ support
        - IAM policies for queue access

    Resources:
        DynamoDB Tables:
            - harrison-jobs: Main job table with GSI
            - harrison-idempotency: TTL-based idempotency keys

        SQS Queues:
            - harrison-jobs-queue: Main processing queue
            - harrison-jobs-dlq: Dead letter queue
            - harrison-jobs-priority: High-priority queue
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Determine removal policy from context
        removal_policy_str = self.node.try_get_context("removalPolicy") or "retain"
        self._removal_policy = (
            RemovalPolicy.DESTROY
            if removal_policy_str == "destroy"
            else RemovalPolicy.RETAIN
        )

        # Get stack prefix from context
        self.stack_prefix = self.node.try_get_context("stackPrefix") or "harrison"

        # ===================================================================
        # VPC for ECS Cluster (exposed for cross-stack reference)
        # ===================================================================
        self.vpc = self._create_vpc()

        # ECS Cluster
        self.ecs_cluster = self._create_ecs_cluster()

        # ===================================================================
        # DynamoDB Tables
        # ===================================================================

        # Jobs Table
        self.jobs_table = self._create_jobs_table()

        # Idempotency Table
        self.idempotency_table = self._create_idempotency_table()

        # ===================================================================
        # SQS Queues
        # ===================================================================

        # Dead Letter Queue (must be created first)
        self.dlq = self._create_dlq()

        # Main Job Queue with DLQ
        self.job_queue = self._create_job_queue()

        # Priority Queue
        self.priority_queue = self._create_priority_queue()

        # ===================================================================
        # Outputs
        # ===================================================================
        self._create_outputs()

    def _create_jobs_table(self) -> dynamodb.Table:
        """
        Create the main jobs DynamoDB table.

        Schema:
            - Partition Key: job_id (String)
            - GSI: user_id-created_at-index (PK: user_id, SK: created_at)

        Billing: Pay-per-request (On-Demand) for cost optimization
        """
        table = dynamodb.Table(
            self,
            "JobsTable",
            table_name=f"{self.stack_prefix}-jobs",
            partition_key=dynamodb.Attribute(
                name="job_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=self._removal_policy,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # GSI for listing user's jobs
        table.add_global_secondary_index(
            index_name="user_id-created_at-index",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # GSI for status filtering
        table.add_global_secondary_index(
            index_name="status-created_at-index",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        return table

    def _create_idempotency_table(self) -> dynamodb.Table:
        """
        Create the idempotency keys DynamoDB table.

        Schema:
            - Partition Key: idempotency_key (String)
            - TTL: expires_at (24 hours from creation)

        Purpose: Prevent duplicate job submissions
        """
        table = dynamodb.Table(
            self,
            "IdempotencyTable",
            table_name=f"{self.stack_prefix}-idempotency",
            partition_key=dynamodb.Attribute(
                name="idempotency_key",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=self._removal_policy,
            time_to_live_attribute="expires_at",
        )

        return table

    def _create_dlq(self) -> sqs.Queue:
        """
        Create the Dead Letter Queue for failed jobs.

        Configuration:
            - Retention: 14 days (for debugging)
            - No redrive policy (messages stay until manually processed)
        """
        dlq = sqs.Queue(
            self,
            "JobsDLQ",
            queue_name=f"{self.stack_prefix}-jobs-dlq",
            retention_period=Duration.days(14),
            removal_policy=self._removal_policy,
        )

        CfnOutput(
            self,
            "DLQArn",
            value=dlq.queue_arn,
            export_name="HarrisonDLQArn",
        ).override_logical_id("DLQArn")

        return dlq

    def _create_job_queue(self) -> sqs.Queue:
        """
        Create the main job processing queue.

        Configuration:
            - Visibility timeout: 60s (time worker has to process)
            - Max receive count: 3 (moves to DLQ after 3 failed attempts)
            - Retention: 24 hours
        """
        queue = sqs.Queue(
            self,
            "JobsQueue",
            queue_name=f"{self.stack_prefix}-jobs-queue",
            visibility_timeout=Duration.seconds(60),
            retention_period=Duration.days(1),
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=self.dlq,
                max_receive_count=3,
            ),
            removal_policy=self._removal_policy,
            encryption=sqs.QueueEncryption.KMS_MANAGED,
        )

        CfnOutput(
            self,
            "JobQueueArn",
            value=queue.queue_arn,
            export_name="HarrisonJobQueueArn",
        ).override_logical_id("JobQueueArn")

        CfnOutput(
            self,
            "JobQueueUrl",
            value=queue.queue_url,
            export_name="HarrisonJobQueueUrl",
        ).override_logical_id("JobQueueUrl")

        return queue

    def _create_priority_queue(self) -> sqs.Queue:
        """
        Create the priority queue for high-priority jobs.

        Configuration:
            - Shorter visibility timeout: 30s (urgent processing)
            - Retention: 24 hours
            - No DLQ (priority jobs are critical)

        Note: High-priority report types (sales_report, financial_report)
              are routed to this queue in the API layer.
        """
        queue = sqs.Queue(
            self,
            "JobsPriorityQueue",
            queue_name=f"{self.stack_prefix}-jobs-priority",
            visibility_timeout=Duration.seconds(30),
            retention_period=Duration.days(1),
            removal_policy=self._removal_policy,
            encryption=sqs.QueueEncryption.KMS_MANAGED,
        )

        CfnOutput(
            self,
            "PriorityQueueArn",
            value=queue.queue_arn,
            export_name="HarrisonPriorityQueueArn",
        ).override_logical_id("PriorityQueueArn")

        CfnOutput(
            self,
            "PriorityQueueUrl",
            value=queue.queue_url,
            export_name="HarrisonPriorityQueueUrl",
        ).override_logical_id("PriorityQueueUrl")

        return queue

    # Properties for cross-stack references
    @property
    def jobs_table_name(self) -> str:
        """Get the jobs table name."""
        return self.jobs_table.table_name

    @property
    def idempotency_table_name(self) -> str:
        """Get the idempotency table name."""
        return self.idempotency_table.table_name

    @property
    def job_queue_url(self) -> str:
        """Get the main job queue URL."""
        return self.job_queue.queue_url

    @property
    def job_queue_arn(self) -> str:
        """Get the main job queue ARN."""
        return self.job_queue.queue_arn

    @property
    def dlq_url(self) -> str:
        """Get the DLQ URL."""
        return self.dlq.queue_url

    @property
    def dlq_arn(self) -> str:
        """Get the DLQ ARN."""
        return self.dlq.queue_arn

    @property
    def priority_queue_url(self) -> str:
        """Get the priority queue URL."""
        return self.priority_queue.queue_url

    @property
    def priority_queue_arn(self) -> str:
        """Get the priority queue ARN."""
        return self.priority_queue.queue_arn

    # ===================================================================
    # VPC and ECS Cluster
    # ===================================================================

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC for ECS cluster."""
        return ec2.Vpc(
            self,
            "VPC",
            vpc_name=f"{self.stack_prefix}-vpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )

    def _create_ecs_cluster(self) -> ecs.Cluster:
        """Create ECS cluster."""
        return ecs.Cluster(
            self,
            "ECSCluster",
            cluster_name=f"{self.stack_prefix}-cluster",
            vpc=self.vpc,
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for cross-stack references."""
        # VPC Output
        CfnOutput(
            self,
            "VPCId",
            value=self.vpc.vpc_id,
            export_name="HarrisonVPCId",
        ).override_logical_id("VPCId")

        # ECS Cluster Output
        CfnOutput(
            self,
            "ECSClusterName",
            value=self.ecs_cluster.cluster_name,
            export_name="HarrisonECSClusterName",
        ).override_logical_id("ECSClusterName")

        # Existing DynamoDB outputs
        CfnOutput(
            self,
            "JobsTableArn",
            value=self.jobs_table.table_arn,
            export_name="HarrisonJobsTableArn",
        ).override_logical_id("JobsTableArn")

        CfnOutput(
            self,
            "JobsTableName",
            value=self.jobs_table.table_name,
            export_name="HarrisonJobsTableName",
        ).override_logical_id("JobsTableName")

        CfnOutput(
            self,
            "IdempotencyTableArn",
            value=self.idempotency_table.table_arn,
            export_name="HarrisonIdempotencyTableArn",
        ).override_logical_id("IdempotencyTableArn")

        CfnOutput(
            self,
            "IdempotencyTableName",
            value=self.idempotency_table.table_name,
            export_name="HarrisonIdempotencyTableName",
        ).override_logical_id("IdempotencyTableName")

        CfnOutput(
            self,
            "DLQUrl",
            value=self.dlq.queue_url,
            export_name="HarrisonDLQUrl",
        ).override_logical_id("DLQUrl")
