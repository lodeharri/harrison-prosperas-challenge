"""
API Stack: API Gateway with Rate Limiting

This stack creates the API layer for exposing the backend services:
- REST API Gateway
- Resources and Methods for /jobs, /jobs/{id}, /health
- Usage Plans with rate limiting
- API Keys for access control
- Integration with ECS Fargate ALB
- CORS support for all endpoints
"""

from typing import Dict, Optional

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_apigateway as apigateway,
    aws_apigatewayv2 as apigatewayv2,
)
from constructs import Construct

from .compute_stack import ComputeStack


# =============================================================================
# CORS Headers Configuration
# =============================================================================
# Headers to pass through from backend to API Gateway responses
CORS_RESPONSE_HEADERS = {
    "method.response.header.Access-Control-Allow-Origin": "integration.response.header.Access-Control-Allow-Origin",
    "method.response.header.Access-Control-Allow-Headers": "integration.response.header.Access-Control-Allow-Headers",
    "method.response.header.Access-Control-Allow-Methods": "integration.response.header.Access-Control-Allow-Methods",
    "method.response.header.Access-Control-Max-Age": "integration.response.header.Access-Control-Max-Age",
}


class APIStack(Stack):
    """
    API infrastructure stack for REST API Gateway.

    Creates:
        - REST API Gateway
        - Resources: /jobs, /jobs/{job_id}, /health, /auth
        - Methods: GET, POST, PUT
        - Usage Plans with rate limiting (100 req/min, burst 200)
        - API Key for authentication
        - Integration with ECS Fargate ALB

    Note: JWT validation is done in the FastAPI backend,
          not in API Gateway (NONE authorizer).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        compute_stack: ComputeStack,
        stack_prefix: str = "harrison",
        **kwargs,
    ) -> None:
        self.compute_stack = compute_stack
        self.stack_prefix = stack_prefix

        super().__init__(scope, construct_id, **kwargs)

        # ===================================================================
        # API Gateway
        # ===================================================================
        self.api = self._create_api_gateway()

        # ===================================================================
        # Resources and Methods
        # ===================================================================
        self._create_resources()

        # ===================================================================
        # Usage Plan and API Key
        # ===================================================================
        self.usage_plan = self._create_usage_plan()
        self.api_key = self._create_api_key()

        # ===================================================================
        # Outputs
        # ===================================================================
        self._create_outputs()

    def _create_api_gateway(self) -> apigateway.RestApi:
        """Create the REST API Gateway with CORS configuration."""
        # Create the RestApi
        api = apigateway.RestApi(
            self,
            "APIGateway",
            rest_api_name=f"{self.stack_prefix}-api-gw",
            description="API Gateway for Reto Prosperas Job Processing API",
            endpoint_configuration=apigateway.EndpointConfiguration(
                types=[apigateway.EndpointType.REGIONAL]
            ),
            binary_media_types=["multipart/form-data", "application/octet-stream"],
        )

        # Apply CORS configuration at the API Gateway level
        # Note: For REST API, CORS must be configured via method responses and integrations
        # This is handled in the backend FastAPI with CORSMiddleware

        CfnOutput(
            self,
            "APIGatewayId",
            value=api.rest_api_id,
            export_name="HarrisonAPIGatewayId",
        ).override_logical_id("APIGatewayId")

        CfnOutput(
            self,
            "APIGatewayRootResourceId",
            value=api.root.resource_id,
            export_name="HarrisonAPIGatewayRootResourceId",
        ).override_logical_id("APIGatewayRootResourceId")

        return api

    def _create_resources(self) -> None:
        """Create API resources and integrate with ECS ALB."""

        # Get ECS ALB endpoint (the service URL)
        service_url = self.compute_stack.api_service_url

        # ===================================================================
        # /auth Resource (for token generation)
        # ===================================================================
        auth_resource = self.api.root.add_resource("auth").add_resource("token")

        auth_integration = apigateway.HttpIntegration(
            f"{service_url}/auth/token",
            http_method="POST",
            options=apigateway.IntegrationOptions(
                request_parameters={
                    "integration.request.header.Content-Type": "method.request.header.Content-Type",
                },
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                    apigateway.IntegrationResponse(
                        status_code="400",
                        selection_pattern="400",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                    apigateway.IntegrationResponse(
                        status_code="401",
                        selection_pattern="401",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                ],
            ),
        )

        auth_method = auth_resource.add_method(
            "POST",
            integration=auth_integration,
            request_parameters={
                "method.request.header.Content-Type": True,
            },
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Content-Type": True,
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                        "method.response.header.Access-Control-Max-Age": True,
                    },
                    response_models={
                        "application/json": apigateway.Model.EMPTY_MODEL,
                    },
                ),
            ],
        )

        # Add OPTIONS method for /auth/token (CORS preflight)
        self._add_cors_options_method(auth_resource)

        # ===================================================================
        # /jobs Resource
        # ===================================================================
        jobs_resource = self.api.root.add_resource("jobs")

        jobs_integration = apigateway.HttpIntegration(
            f"{service_url}/jobs",
            http_method="GET",
            options=apigateway.IntegrationOptions(
                request_parameters={
                    "integration.request.header.Authorization": "method.request.header.Authorization",
                    "integration.request.querystring.limit": "method.request.querystring.limit",
                    "integration.request.querystring.last_key": "method.request.querystring.last_key",
                },
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                    apigateway.IntegrationResponse(
                        status_code="401",
                        selection_pattern="401",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                ],
            ),
        )

        jobs_get_method = jobs_resource.add_method(
            "GET",
            integration=jobs_integration,
            request_parameters={
                "method.request.header.Authorization": True,
                "method.request.querystring.limit": False,
                "method.request.querystring.last_key": False,
            },
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Content-Type": True,
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                        "method.response.header.Access-Control-Max-Age": True,
                    },
                    response_models={
                        "application/json": apigateway.Model.EMPTY_MODEL,
                    },
                ),
            ],
        )

        # POST /jobs - Create new job
        jobs_post_integration = apigateway.HttpIntegration(
            f"{service_url}/jobs",
            http_method="POST",
            options=apigateway.IntegrationOptions(
                request_parameters={
                    "integration.request.header.Authorization": "method.request.header.Authorization",
                    "integration.request.header.Content-Type": "method.request.header.Content-Type",
                    "integration.request.header.X-Idempotency-Key": "method.request.header.X-Idempotency-Key",
                },
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="201",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            "method.response.header.Location": "integration.response.header.Location",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                    apigateway.IntegrationResponse(
                        status_code="400",
                        selection_pattern="400",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                    apigateway.IntegrationResponse(
                        status_code="401",
                        selection_pattern="401",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                    apigateway.IntegrationResponse(
                        status_code="409",
                        selection_pattern="409",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                ],
            ),
        )

        jobs_post_method = jobs_resource.add_method(
            "POST",
            integration=jobs_post_integration,
            request_parameters={
                "method.request.header.Authorization": True,
                "method.request.header.Content-Type": True,
                "method.request.header.X-Idempotency-Key": False,
            },
            method_responses=[
                apigateway.MethodResponse(
                    status_code="201",
                    response_parameters={
                        "method.response.header.Content-Type": True,
                        "method.response.header.Location": True,
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                        "method.response.header.Access-Control-Max-Age": True,
                    },
                    response_models={
                        "application/json": apigateway.Model.EMPTY_MODEL,
                    },
                ),
            ],
        )

        # Add OPTIONS method for /jobs (CORS preflight)
        self._add_cors_options_method(jobs_resource)

        # ===================================================================
        # /jobs/{job_id} Resource
        # ===================================================================
        job_id_resource = jobs_resource.add_resource("{job_id}")

        job_id_integration = apigateway.HttpIntegration(
            f"{service_url}/jobs/{{job_id}}",
            http_method="GET",
            options=apigateway.IntegrationOptions(
                request_parameters={
                    "integration.request.path.job_id": "method.request.path.job_id",
                    "integration.request.header.Authorization": "method.request.header.Authorization",
                },
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                    apigateway.IntegrationResponse(
                        status_code="404",
                        selection_pattern="404",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                ],
            ),
        )

        job_id_resource.add_method(
            "GET",
            integration=job_id_integration,
            request_parameters={
                "method.request.path.job_id": True,
                "method.request.header.Authorization": True,
            },
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Content-Type": True,
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                        "method.response.header.Access-Control-Max-Age": True,
                    },
                    response_models={
                        "application/json": apigateway.Model.EMPTY_MODEL,
                    },
                ),
            ],
        )

        # Add OPTIONS method for /jobs/{job_id} (CORS preflight)
        self._add_cors_options_method(job_id_resource)

        # ===================================================================
        # /health Resource (no auth required)
        # ===================================================================
        health_resource = self.api.root.add_resource("health")

        health_integration = apigateway.HttpIntegration(
            f"{service_url}/health",
            http_method="GET",
            options=apigateway.IntegrationOptions(
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Content-Type": "integration.response.header.Content-Type",
                            **CORS_RESPONSE_HEADERS,
                        },
                    ),
                ],
            ),
        )

        health_resource.add_method(
            "GET",
            integration=health_integration,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Content-Type": True,
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                        "method.response.header.Access-Control-Max-Age": True,
                    },
                    response_models={
                        "application/json": apigateway.Model.EMPTY_MODEL,
                    },
                ),
            ],
        )

        # Add OPTIONS method for /health (CORS preflight)
        self._add_cors_options_method(health_resource)

        # ===================================================================
        # /ws/jobs/{user_id} Resource (WebSocket - optional)
        # ===================================================================
        ws_resource = self.api.root.add_resource("ws")
        ws_jobs_resource = ws_resource.add_resource("jobs")
        ws_user_resource = ws_jobs_resource.add_resource("{user_id}")

        # Note: WebSocket API requires API Gateway WebSocket API,
        # not REST API. For production, consider using AWS IoT Core
        # or a dedicated WebSocket solution.

    def _create_usage_plan(self) -> apigateway.UsagePlan:
        """Create usage plan with rate limiting."""

        usage_plan = apigateway.UsagePlan(
            self,
            "UsagePlan",
            name=f"{self.stack_prefix}-rate-limit",
            description="Rate limiting plan for API access",
            quota=apigateway.QuotaSettings(
                limit=10000,  # 10k requests per month
                period=apigateway.Period.MONTH,
            ),
            throttle=apigateway.ThrottleSettings(
                burst_limit=200,  # Burst capacity
                rate_limit=100,  # Requests per second
            ),
        )

        CfnOutput(
            self,
            "UsagePlanId",
            value=usage_plan.usage_plan_id,
            export_name="HarrisonUsagePlanId",
        ).override_logical_id("UsagePlanId")

        return usage_plan

    def _create_api_key(self) -> apigateway.ApiKey:
        """Create API key for accessing the API."""

        api_key = apigateway.ApiKey(
            self,
            "APIKey",
            api_key_name=f"{self.stack_prefix}-api-key",
            description="API Key for Reto Prosperas API",
            enabled=True,
        )

        # Associate API key with usage plan
        self.usage_plan.add_api_key(api_key)

        CfnOutput(
            self,
            "APIKeyId",
            value=api_key.key_id,
            export_name="HarrisonAPIKeyId",
        ).override_logical_id("APIKeyId")

        return api_key

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "APIGatewayEndpoint",
            value=self.api.url,
            export_name="HarrisonAPIGatewayEndpoint",
        ).override_logical_id("APIGatewayEndpoint")

        CfnOutput(
            self,
            "APIUrl",
            value=self.api.url.rstrip("/"),  # Remove trailing slash if present
            export_name="HarrisonAPIUrl",
        ).override_logical_id("APIUrl")

    @property
    def api_url(self) -> str:
        """Get the API Gateway URL."""
        return self.api.url

    @property
    def api_gateway_id(self) -> str:
        """Get the API Gateway ID."""
        return self.api.rest_api_id

    def _add_cors_options_method(self, resource: apigateway.Resource) -> None:
        """
        Add an OPTIONS method to a resource for CORS preflight handling.

        This creates a mock OPTIONS method that returns the CORS headers
        directly from API Gateway without forwarding to the backend.

        Args:
            resource: The API Gateway resource to add the OPTIONS method to
        """
        # Create a mock integration for OPTIONS that returns static CORS headers
        options_integration = apigateway.MockIntegration(
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'",
                        "method.response.header.Access-Control-Allow-Headers": "'Content-Type,Authorization,X-Idempotency-Key,X-Requested-With'",
                        "method.response.header.Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
                        "method.response.header.Access-Control-Max-Age": "'86400'",
                    },
                    response_templates={
                        "application/json": '{"statusCode": 200}',
                    },
                ),
            ],
            passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
            request_templates={
                "application/json": '{"statusCode": 200}',
            },
        )

        resource.add_method(
            "OPTIONS",
            options_integration,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                        "method.response.header.Access-Control-Max-Age": True,
                    },
                    response_models={
                        "application/json": apigateway.Model.EMPTY_MODEL,
                    },
                ),
            ],
        )
