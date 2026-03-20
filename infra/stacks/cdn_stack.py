"""
CDN Stack: S3 Static Hosting and CloudFront Distribution

This stack creates the CDN layer for serving the frontend:
- S3 bucket for static website hosting
- CloudFront distribution for global content delivery
- Origin Access Identity (OAI) for S3 protection
- CloudFront Functions for URL rewriting (SPA routing)
"""

from typing import Optional

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
)
from constructs import Construct


class CDNStack(Stack):
    """
    CDN infrastructure stack for frontend hosting.

    Creates:
        - S3 bucket for static website hosting
        - CloudFront distribution with global edge caching
        - Origin Access Identity (OAI) for S3 protection
        - CloudFront Function for SPA routing
        - S3 deployment for frontend assets

    Note: The frontend uses VITE_ environment variables for build-time
          configuration (API URL, WebSocket URL).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        api_url: str = "",
        stack_prefix: str = "harrison",
        **kwargs,
    ) -> None:
        self.stack_prefix = stack_prefix
        self.api_url = api_url

        super().__init__(scope, construct_id, **kwargs)

        # Determine removal policy from context
        removal_policy_str = self.node.try_get_context("removalPolicy") or "retain"
        self._removal_policy = (
            RemovalPolicy.DESTROY
            if removal_policy_str == "destroy"
            else RemovalPolicy.RETAIN
        )

        # ===================================================================
        # S3 Bucket
        # ===================================================================
        self.bucket = self._create_s3_bucket()

        # ===================================================================
        # Origin Access Identity (OAI)
        # ===================================================================
        self.oai = self._create_oai()

        # ===================================================================
        # CloudFront Distribution
        # ===================================================================
        self.distribution = self._create_cloudfront_distribution()

        # ===================================================================
        # S3 Deployment (optional, for local builds)
        # ===================================================================
        self._create_s3_deployment()

        # ===================================================================
        # Outputs
        # ===================================================================
        self._create_outputs()

    def _create_s3_bucket(self) -> s3.Bucket:
        """
        Create S3 bucket for static website hosting.

        Configuration:
            - PublicReadAccess: False (protected by OAI)
            - Website index document: index.html
            - Website error document: index.html (SPA fallback)
            - Versioning enabled
            - Server-side encryption
        """
        bucket = s3.Bucket(
            self,
            "FrontendBucket",
            bucket_name=f"{self.stack_prefix}-frontend",
            public_read_access=False,  # Protected by CloudFront OAI
            website_index_document="index.html",
            website_error_document="index.html",  # SPA routing fallback
            versioned=True,
            removal_policy=self._removal_policy,
            encryption=s3.BucketEncryption.S3_MANAGED,
            cors=[
                s3.CorsRule(
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.HEAD,
                    ],
                    allowed_origins=[
                        "*",  # In production, restrict to CloudFront domain
                    ],
                    allowed_headers=["*"],
                    max_age=3600,
                )
            ],
        )

        CfnOutput(
            self,
            "FrontendBucketName",
            value=bucket.bucket_name,
            export_name="HarrisonFrontendBucketName",
        ).override_logical_id("FrontendBucketName")

        CfnOutput(
            self,
            "FrontendBucketArn",
            value=bucket.bucket_arn,
            export_name="HarrisonFrontendBucketArn",
        ).override_logical_id("FrontendBucketArn")

        return bucket

    def _create_oai(self) -> cloudfront.OriginAccessIdentity:
        """
        Create Origin Access Identity for CloudFront to access S3.

        This ensures only CloudFront can access the S3 bucket,
        preventing direct bucket access.
        """
        oai = cloudfront.OriginAccessIdentity(
            self,
            "OriginAccessIdentity",
            comment=f"OAI for {self.stack_prefix} frontend distribution",
        )

        # Add bucket policy to allow access only from CloudFront via OAI
        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                principals=[oai.grant_principal],
                resources=[f"{self.bucket.bucket_arn}/*"],
            )
        )

        CfnOutput(
            self,
            "OriginAccessIdentityId",
            value=oai.origin_access_identity_id,
            export_name="HarrisonOriginAccessIdentityId",
        ).override_logical_id("OriginAccessIdentityId")

        return oai

    def _create_cloudfront_distribution(self) -> cloudfront.CfnDistribution:
        """
        Create CloudFront distribution with S3 origin.

        Configuration:
            - Price class: North America + Europe (cost optimization)
            - Default TTL: 86400 (1 day)
            - Min TTL: 3600 (1 hour)
            - Max TTL: 31536000 (1 year)
            - Viewer Protocol Policy: Redirect HTTP to HTTPS
            - Compress: Enabled (gzip/brotli)
        """
        # Create CloudFront function for SPA routing
        spa_routing_function = self._create_spa_routing_function()

        distribution = cloudfront.CfnDistribution(
            self,
            "FrontendDistribution",
            distribution_config=cloudfront.CfnDistribution.DistributionConfigProperty(
                enabled=True,
                comment=f"CloudFront distribution for {self.stack_prefix} frontend",
                price_class=cloudfront.PriceClass.PRICE_CLASS_100.value,  # NA + EU
                http_version="http2and3",
                default_root_object="index.html",
                viewer_certificate=cloudfront.CfnDistribution.ViewerCertificateProperty(
                    cloud_front_default_certificate=True,
                ),
                # CDK v2: Use 'origins' and 'default_cache_behavior' separately
                origins=[
                    cloudfront.CfnDistribution.OriginProperty(
                        id="frontend",
                        domain_name=self.bucket.bucket_name,
                        s3_origin_config=cloudfront.CfnDistribution.S3OriginConfigProperty(
                            origin_access_identity=(
                                f"origin-access-identity/cloudfront/{self.oai.origin_access_identity_id}"
                            ),
                        ),
                        connection_attempts=3,
                        connection_timeout=10,
                    )
                ],
                default_cache_behavior=cloudfront.CfnDistribution.DefaultCacheBehaviorProperty(
                    target_origin_id="frontend",
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS.value,
                    compress=True,
                    allowed_methods=["GET", "HEAD", "OPTIONS"],
                    cached_methods=["GET", "HEAD", "OPTIONS"],
                    default_ttl=Duration.days(1).to_seconds(),
                    min_ttl=Duration.hours(1).to_seconds(),
                    max_ttl=Duration.days(365).to_seconds(),
                    function_associations=[
                        cloudfront.CfnDistribution.FunctionAssociationProperty(
                            function_arn=spa_routing_function.function_arn,
                            event_type="viewer-request",
                        )
                    ],
                    forwarded_values=cloudfront.CfnDistribution.ForwardedValuesProperty(
                        query_string=False,
                        headers=["Accept", "Origin"],
                        cookies=cloudfront.CfnDistribution.CookiesProperty(
                            forward="none",
                        ),
                    ),
                ),
                custom_error_responses=[
                    cloudfront.CfnDistribution.CustomErrorResponseProperty(
                        error_code=403,
                        response_code=200,
                        response_page_path="/index.html",
                    ),
                    cloudfront.CfnDistribution.CustomErrorResponseProperty(
                        error_code=404,
                        response_code=200,
                        response_page_path="/index.html",
                    ),
                ],
            ),
        )

        CfnOutput(
            self,
            "DistributionId",
            value=distribution.ref,
            export_name="HarrisonDistributionId",
        ).override_logical_id("DistributionId")

        CfnOutput(
            self,
            "DistributionDomainName",
            value=distribution.attr_domain_name,
            export_name="HarrisonDistributionDomainName",
        ).override_logical_id("DistributionDomainName")

        return distribution

    def _create_spa_routing_function(self) -> cloudfront.Function:
        """
        Create CloudFront Function for SPA routing.

        This function ensures that all requests (except static assets)
        are routed to index.html for client-side routing.
        """
        function_code = """
function handler(event) {
    var request = event.request;
    var uri = request.uri;
    
    // Check if the request is for a static asset
    var staticExtensions = [
        '.html', '.htm', '.css', '.js', '.json', '.png', '.jpg', 
        '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', 
        '.ttf', '.eot', '.webp', '.map'
    ];
    
    // Check if URI has a file extension
    var hasExtension = false;
    for (var i = 0; i < staticExtensions.length; i++) {
        if (uri.indexOf(staticExtensions[i]) !== -1) {
            hasExtension = true;
            break;
        }
    }
    
    // If no extension or not a static asset, serve index.html
    if (!hasExtension || uri === '/') {
        request.uri = '/index.html';
    }
    
    return request;
}
"""
        function = cloudfront.Function(
            self,
            "SPARoutingFunction",
            function_name=f"{self.stack_prefix}-spa-routing",
            code=cloudfront.FunctionCode.from_inline(function_code),
            runtime=cloudfront.FunctionRuntime.JS_1_0,
            comment="CloudFront Function for SPA routing",
        )

        return function

    def _create_s3_deployment(self) -> Optional[s3_deployment.BucketDeployment]:
        """
        Create S3 deployment for frontend assets.

        This is optional and can be used for local development.
        In CI/CD, the frontend should be built and deployed separately.

        Note: This deployment uses a placeholder. In production,
        run `npm run build` first and deploy the `dist` folder.
        """
        # Check if frontend exists
        frontend_path = "../frontend/dist"

        try:
            import os

            if not os.path.exists(frontend_path):
                # Frontend not built yet - skip deployment
                # In CI/CD, build and deploy separately
                return None

            deployment = s3_deployment.BucketDeployment(
                self,
                "FrontendDeployment",
                sources=[s3_deployment.Source.asset(frontend_path)],
                destination_bucket=self.bucket,
                distribution=self.distribution,
                distribution_paths=["/*"],
            )

            return deployment

        except Exception:
            # Frontend not built yet
            return None

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "FrontendBucketWebsiteUrl",
            value=self.bucket.bucket_website_url,
            export_name="HarrisonFrontendBucketWebsiteUrl",
        ).override_logical_id("FrontendBucketWebsiteUrl")

        CfnOutput(
            self,
            "FrontendUrl",
            value=f"https://{self.distribution.attr_domain_name}",
            export_name="HarrisonFrontendUrl",
        ).override_logical_id("FrontendUrl")

    @property
    def distribution_url(self) -> str:
        """Get the CloudFront distribution URL."""
        return f"https://{self.distribution.attr_domain_name}"

    @property
    def bucket_name(self) -> str:
        """Get the S3 bucket name."""
        return self.bucket.bucket_name
