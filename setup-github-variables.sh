#!/bin/bash
set -e

echo "=== Configuración de variables de GitHub para despliegue desde cero ==="
echo ""

# Variables a configurar
VARIABLES=(
  "CDK_BOOTSTRAPPED=false"
  "AWS_REGION=us-east-1"
  "STACK_PREFIX=harrison"
  "CDK_APP_NAME=harrison-prosperas-challenge"
  "ECR_REPOSITORY=harrison-prospera-challenge"
  "FRONTEND_BUCKET=harrison-frontend"
  "CI_API_URL=http://localhost:8000"
  "CI_WS_URL=ws://localhost:8000"
)

echo "Configurando variables de GitHub..."
echo "-----------------------------------"

for VAR in "${VARIABLES[@]}"; do
  NAME="${VAR%%=*}"
  VALUE="${VAR#*=}"
  
  echo "Configurando $NAME=$VALUE"
  
  # Usar GitHub CLI para configurar variable
  if command -v gh &> /dev/null; then
    gh variable set "$NAME" --body "$VALUE"
    echo "  ✓ Configurada con GitHub CLI"
  else
    echo "  ⚠ GitHub CLI no encontrado. Configura manualmente:"
    echo "    - Nombre: $NAME"
    echo "    - Valor: $VALUE"
    echo ""
  fi
done

echo ""
echo "=== Verificación de secrets requeridos ==="
echo ""

# Secrets requeridos
REQUIRED_SECRETS=(
  "AWS_ACCESS_KEY_ID"
  "AWS_SECRET_ACCESS_KEY"
  "AWS_ACCOUNT_ID"
  "JWT_SECRET_KEY"
)

echo "Secrets requeridos para el despliegue:"
echo "---------------------------------------"

for SECRET in "${REQUIRED_SECRETS[@]}"; do
  echo "- $SECRET"
done

echo ""
echo "=== Instrucciones para configuración manual ==="
echo ""
echo "1. Variables de GitHub (Settings > Secrets and variables > Actions > Variables):"
echo "   - CDK_BOOTSTRAPPED: false"
echo "   - AWS_REGION: us-east-1"
echo "   - STACK_PREFIX: harrison"
echo "   - CDK_APP_NAME: harrison-prosperas-challenge"
echo "   - ECR_REPOSITORY: harrison-prospera-challenge"
echo "   - FRONTEND_BUCKET: harrison-frontend"
echo "   - CI_API_URL: http://localhost:8000"
echo "   - CI_WS_URL: ws://localhost:8000"
echo ""
echo "2. Secrets de GitHub (Settings > Secrets and variables > Actions > Secrets):"
echo "   - AWS_ACCESS_KEY_ID: Tu AWS Access Key ID"
echo "   - AWS_SECRET_ACCESS_KEY: Tu AWS Secret Access Key"
echo "   - AWS_ACCOUNT_ID: Tu AWS Account ID"
echo "   - JWT_SECRET_KEY: Genera con: openssl rand -base64 64"
echo ""
echo "3. Permisos IAM requeridos para las credenciales AWS:"
echo "   - ECR: Crear repositorio, push/pull imágenes"
echo "   - CloudFormation: Crear/eliminar stacks"
echo "   - S3: Crear bucket, subir archivos"
echo "   - CloudFront: Crear distribución, invalidar cache"
echo "   - DynamoDB: Crear/eliminar tablas"
echo "   - SQS: Crear/eliminar colas"
echo "   - App Runner: Crear/eliminar servicios"
echo "   - API Gateway: Crear/eliminar APIs"
echo ""
echo "=== Configuración lista para despliegue desde cero ==="