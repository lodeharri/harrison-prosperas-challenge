# Pendiente: Error de CORS en API Gateway

## Problema Actual
Error de CORS (Cross-Origin Resource Sharing) al intentar acceder a la API REST desde el frontend desplegado en CloudFront.

**Síntoma:** El frontend en `https://d32qctmfn9gmhs.cloudfront.net` no puede realizar peticiones a la API en `https://l70wtmolkb.execute-api.us-east-1.amazonaws.com/prod/` debido a restricciones de CORS.

## URLs de Producción Actuales

| Componente | URL |
|------------|-----|
| **Frontend (CloudFront)** | `https://d32qctmfn9gmhs.cloudfront.net` |
| **API REST (API Gateway)** | `https://l70wtmolkb.execute-api.us-east-1.amazonaws.com/prod/` |
| **WebSocket (ALB via CloudFront)** | `wss://d32qctmfn9gmhs.cloudfront.net/ws/jobs` |

## Configuración AWS

- **Región:** `us-east-1`
- **Perfil AWS usado:** `harrison-cicd`
- **Stack CDK:** `harrison-api-stack` (API Gateway REST)
- **Stack CDK:** `harrison-cdn-stack` (CloudFront + S3)

## Posible Falla

### 1. Configuración de CORS en API Gateway
La API Gateway REST (`harrison-api-stack`) puede no tener configuradas las cabeceras CORS necesarias para permitir peticiones desde el dominio del frontend.

**Cabeceras CORS requeridas:**
- `Access-Control-Allow-Origin: https://d32qctmfn9gmhs.cloudfront.net`
- `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type, Authorization`

### 2. Configuración de OPTIONS en API Gateway
Falta posiblemente el método `OPTIONS` para manejar preflight requests.

### 3. Configuración en FastAPI
El backend FastAPI puede necesitar middleware CORS configurado para el dominio específico.

## Lo que Hemos Hecho Hasta Ahora

### ✅ Despliegue Exitoso a AWS
- Infraestructura completa desplegada (VPC, ECS, ALB, API Gateway, CloudFront)
- Frontend SPA desplegado en S3 + CloudFront
- API REST desplegada en API Gateway + ECS Fargate
- WebSocket funcionando via ALB + CloudFront

### ✅ Corrección de Workflow CI/CD
- Modificado `.github/workflows/deploy.yml` para usar HTTPS/WSS
- Actualizada la dependencia: `build-frontend` ahora depende de `deploy-cdk`
- URLs actualizadas en `AGENTS.md` y documentación

### ✅ URLs Actualizadas
- Frontend: CloudFront distribution
- API: API Gateway REST endpoint
- WebSocket: ALB via CloudFront (conversión automática ws:// → wss://)

## Pasos para Resolver

### 1. Verificar configuración actual de CORS en API Gateway
```bash
aws apigatewayv2 get-api --api-id l70wtmolkb --profile harrison-cicd
aws apigatewayv2 get-cors --api-id l70wtmolkb --profile harrison-cicd
```

### 2. Actualizar CDK para incluir CORS
Modificar `infra/stacks/api_stack.py` para agregar configuración CORS:

```python
# En harrison_api_stack.py
api = apigw.RestApi(
    self,
    "HarrisonApi",
    rest_api_name="harrison-api",
    deploy_options=apigw.StageOptions(
        stage_name="prod",
        throttling_rate_limit=100,
        throttling_burst_limit=200,
    ),
    default_cors_preflight_options=apigw.CorsOptions(
        allow_origins=["https://d32qctmfn9gmhs.cloudfront.net"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=Duration.days(1),
    ),
)
```

### 3. Verificar middleware CORS en FastAPI
Revisar `backend/src/adapters/primary/fastapi/app.py` para asegurar que tiene:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://d32qctmfn9gmhs.cloudfront.net"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4. Re-desplegar después de los cambios
```bash
# Actualizar CDK
cdk deploy harrison-api-stack --profile harrison-cicd

# Verificar cambios
curl -v -X OPTIONS https://l70wtmolkb.execute-api.us-east-1.amazonaws.com/prod/health \
  -H "Origin: https://d32qctmfn9gmhs.cloudfront.net" \
  -H "Access-Control-Request-Method: GET"
```

## Comandos de Verificación

### Verificar estado actual:
```bash
# Verificar que API responde
curl https://l70wtmolkb.execute-api.us-east-1.amazonaws.com/prod/health

# Verificar CORS headers
curl -v -X OPTIONS https://l70wtmolkb.execute-api.us-east-1.amazonaws.com/prod/health \
  -H "Origin: https://d32qctmolkb.execute-api.us-east-1.amazonaws.com" \
  -H "Access-Control-Request-Method: GET"
```

### Verificar CloudFront:
```bash
# Obtener distribución CloudFront
aws cloudfront list-distributions --profile harrison-cicd \
  --query "DistributionList.Items[?contains(Comment, 'harrison')]"

# Verificar configuración ALB
aws elbv2 describe-load-balancers --profile harrison-cicd \
  --query "LoadBalancers[?contains(LoadBalancerName, 'harrison')]"
```

## Referencias

- [AGENTS.md](./AGENTS.md) - Documentación principal del proyecto
- [.github/workflows/deploy.yml](./.github/workflows/deploy.yml) - Pipeline CI/CD
- [infra/stacks/api_stack.py](./infra/stacks/api_stack.py) - Configuración API Gateway
- [backend/src/adapters/primary/fastapi/app.py](./backend/src/adapters/primary/fastapi/app.py) - Configuración FastAPI

---

**Fecha:** 22 de marzo de 2026  
**Estado:** Pendiente de resolución  
**Prioridad:** Alta (bloquea integración frontend-backend)