# Despliegue desde Cero - Reto Prosperas

Este documento describe los pasos para desplegar completamente desde cero el proyecto Harrison Prosperas Challenge en AWS usando GitHub Actions.

## Estado Actual

✅ **Recursos AWS limpiados:** No hay recursos existentes en AWS relacionados con el proyecto.
✅ **Workflow actualizado:** El workflow `deploy.yml` ha sido mejorado para:
   - Extracción robusta de outputs de CDK
   - Generación correcta de URL WebSocket
   - Actualización automática de `CLOUDFRONT_DISTRIBUTION_ID`
   - Bootstrap condicional de CDK

## Pasos para el Despliegue

### 1. Configurar Variables de GitHub

Ejecuta el script de configuración:

```bash
./setup-github-variables.sh
```

O configura manualmente en GitHub:
- **Settings > Secrets and variables > Actions > Variables**
- Agrega las siguientes variables:

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `CDK_BOOTSTRAPPED` | `false` | Indica que CDK necesita bootstrap |
| `AWS_REGION` | `us-east-1` | Región AWS para despliegue |
| `STACK_PREFIX` | `harrison` | Prefijo para nombres de recursos |
| `CDK_APP_NAME` | `harrison-prosperas-challenge` | Nombre de la app CDK |
| `ECR_REPOSITORY` | `harrison-prospera-challenge` | Nombre del repositorio ECR |
| `FRONTEND_BUCKET` | `harrison-frontend` | Bucket S3 para frontend |
| `CI_API_URL` | `http://localhost:8000` | URL API para builds CI |
| `CI_WS_URL` | `ws://localhost:8000` | URL WebSocket para builds CI |

### 2. Configurar Secrets de GitHub

**Settings > Secrets and variables > Actions > Secrets**

| Secret | Descripción | Cómo obtener |
|--------|-------------|--------------|
| `AWS_ACCESS_KEY_ID` | AWS Access Key ID | Desde AWS IAM |
| `AWS_SECRET_ACCESS_KEY` | AWS Secret Access Key | Desde AWS IAM |
| `AWS_ACCOUNT_ID` | AWS Account ID | Desde AWS Console |
| `JWT_SECRET_KEY` | Clave para firmar JWT | Generar: `openssl rand -base64 64` |

### 3. Permisos IAM Requeridos

Las credenciales AWS necesitan los siguientes permisos:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:*",
        "cloudformation:*",
        "s3:*",
        "cloudfront:*",
        "dynamodb:*",
        "sqs:*",
        "apprunner:*",
        "apigateway:*",
        "secretsmanager:*",
        "iam:*",
        "logs:*",
        "events:*"
      ],
      "Resource": "*"
    }
  ]
}
```

### 4. Ejecutar el Despliegue

El despliegue se activa automáticamente al hacer push a la rama `master`. Para forzar un despliegue:

1. **Merge a master:** Si estás en una rama feature
2. **O crear un commit vacío:**
   ```bash
   git commit --allow-empty -m "Trigger deployment"
   git push origin master
   ```

### 5. Flujo del Despliegue

El workflow `deploy.yml` ejecuta 6 jobs en orden:

1. **build-ecr:** Construye y sube imagen Docker a ECR
2. **cdk-synth:** Sintetiza templates CDK, extrae outputs (API URL, CloudFront ID)
3. **build-frontend:** Construye frontend con URLs de producción
4. **deploy-cdk:** Despliega 4 stacks CDK:
   - `harrison-data-stack` (DynamoDB + SQS)
   - `harrison-compute-stack` (App Runner API + Worker)
   - `harrison-api-stack` (API Gateway + Rate Limiting)
   - `harrison-cdn-stack` (S3 + CloudFront)
5. **deploy-frontend:** Sube frontend a S3, invalida CloudFront
6. **verify:** Health check y smoke test

### 6. Verificación Post-Despliegue

Después del despliegue, verifica:

1. **API Gateway:** `https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/health`
2. **Frontend:** `https://<cloudfront-id>.cloudfront.net`
3. **CloudFormation:** 4 stacks en estado `CREATE_COMPLETE`
4. **ECR:** Imagen Docker subida
5. **S3:** Archivos del frontend en el bucket

## Recursos que se Crearán

### Stacks de CloudFormation
- `harrison-data-stack` (DynamoDB, SQS)
- `harrison-compute-stack` (App Runner)
- `harrison-api-stack` (API Gateway)
- `harrison-cdn-stack` (S3, CloudFront)

### Recursos AWS
- **DynamoDB:** `harrison-jobs`, `harrison-idempotency`
- **SQS:** `harrison-jobs-queue`, `harrison-jobs-dlq`, `harrison-jobs-priority`
- **ECR:** `harrison-prospera-challenge`
- **S3:** `harrison-frontend`
- **CloudFront:** Distribución para frontend
- **App Runner:** `harrison-api`, `harrison-worker`
- **API Gateway:** API REST con WebSocket
- **Secrets Manager:** `harrison-jwt-secret`

## Solución de Problemas

### CDK Bootstrap Falla
Si el bootstrap falla:
1. Verifica `AWS_ACCOUNT_ID` en secrets
2. Verifica permisos IAM
3. Ejecuta manualmente:
   ```bash
   cd infra
   npx cdk bootstrap aws://<account-id>/us-east-1
   ```

### Extracción de Outputs Falla
El workflow tiene métodos de fallback:
1. Intenta con `cdk list --all`
2. Sintetiza stacks individualmente
3. Extrae de templates CloudFormation

### CloudFront ID no se Actualiza
El workflow actualiza automáticamente `CLOUDFRONT_DISTRIBUTION_ID` después del despliegue del stack CDN.

### Health Check Falla
- Espera 2-3 minutos después del despliegue
- Verifica logs de App Runner
- Revisa configuración de API Gateway

## Costo Estimado

| Servicio | Configuración | Costo Mensual |
|----------|---------------|---------------|
| App Runner | 1 vCPU, 2 GB | ~$5-7 |
| DynamoDB | On-demand | ~$0-1 |
| SQS | Standard | ~$0* |
| ECR | Storage | ~$0.05 |
| CloudFront | Pay-as-you-go | ~$0.02 |
| S3 | Standard | ~$0.01 |
| **Total** | | **~$5-8** |

*Primer 1M requests/mes gratis

## Limpieza

Para eliminar todos los recursos:

```bash
./cleanup-aws-resources.sh
```

O manualmente:
1. Eliminar stacks CloudFormation
2. Eliminar bucket S3
3. Eliminar repositorio ECR
4. Eliminar distribución CloudFront

## Referencias

- [Workflow deploy.yml](.github/workflows/deploy.yml)
- [Script de limpieza](cleanup-aws-resources.sh)
- [Script de configuración](setup-github-variables.sh)
- [Documentación CDK](infra/README.md)