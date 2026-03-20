#!/bin/bash
set -e

echo "=== Limpieza de recursos AWS para proyecto Harrison ==="
echo ""

# Configuración
AWS_REGION="us-east-1"
STACK_PREFIX="harrison"
ECR_REPOSITORY="harrison-prospera-challenge"
FRONTEND_BUCKET="harrison-frontend"
SECRET_NAME="harrison-jwt-secret"

echo "1. Verificando stacks de CloudFormation..."
echo "-------------------------------------------"

# Listar stacks
STACKS=$(aws cloudformation list-stacks \
  --query "StackSummaries[?contains(StackName, '$STACK_PREFIX') && StackStatus!='DELETE_COMPLETE'].StackName" \
  --output text 2>/dev/null || echo "")

if [ -n "$STACKS" ]; then
  echo "Stacks encontrados:"
  for STACK in $STACKS; do
    echo "  - $STACK"
  done
  
  echo ""
  echo "Eliminando stacks..."
  for STACK in $STACKS; do
    echo "  Eliminando $STACK..."
    aws cloudformation delete-stack --stack-name "$STACK" --region "$AWS_REGION"
    echo "  Esperando eliminación de $STACK..."
    aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$AWS_REGION"
  done
  echo "✓ Todos los stacks eliminados"
else
  echo "✓ No hay stacks para eliminar"
fi

echo ""
echo "2. Verificando repositorio ECR..."
echo "---------------------------------"

# Verificar repositorio ECR
if aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "Repositorio ECR encontrado: $ECR_REPOSITORY"
  
  # Eliminar todas las imágenes primero
  echo "  Eliminando imágenes..."
  IMAGES=$(aws ecr list-images --repository-name "$ECR_REPOSITORY" --region "$AWS_REGION" --query 'imageIds[*]' --output json)
  if [ "$IMAGES" != "[]" ]; then
    echo "$IMAGES" | jq -c '.[]' | while read -r IMAGE; do
      aws ecr batch-delete-image \
        --repository-name "$ECR_REPOSITORY" \
        --image-ids "$IMAGE" \
        --region "$AWS_REGION"
    done
  fi
  
  # Eliminar repositorio
  echo "  Eliminando repositorio..."
  aws ecr delete-repository --repository-name "$ECR_REPOSITORY" --force --region "$AWS_REGION"
  echo "✓ Repositorio ECR eliminado"
else
  echo "✓ No hay repositorio ECR para eliminar"
fi

echo ""
echo "3. Verificando bucket S3..."
echo "---------------------------"

# Verificar bucket S3
if aws s3api head-bucket --bucket "$FRONTEND_BUCKET" --region "$AWS_REGION" 2>/dev/null; then
  echo "Bucket S3 encontrado: $FRONTEND_BUCKET"
  
  # Vaciar bucket
  echo "  Vaciando bucket..."
  aws s3 rm "s3://$FRONTEND_BUCKET" --recursive --region "$AWS_REGION"
  
  # Eliminar bucket
  echo "  Eliminando bucket..."
  aws s3api delete-bucket --bucket "$FRONTEND_BUCKET" --region "$AWS_REGION"
  echo "✓ Bucket S3 eliminado"
else
  echo "✓ No hay bucket S3 para eliminar"
fi

echo ""
echo "4. Verificando distribución CloudFront..."
echo "----------------------------------------"

# Buscar distribuciones CloudFront
CF_DISTRIBUTIONS=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?contains(Comment, '$STACK_PREFIX') || contains(Origins.Items[0].DomainName, '$FRONTEND_BUCKET')].Id" \
  --output text 2>/dev/null || echo "")

if [ -n "$CF_DISTRIBUTIONS" ]; then
  echo "Distribuciones CloudFront encontradas:"
  for DIST_ID in $CF_DISTRIBUTIONS; do
    echo "  - $DIST_ID"
    
    # Deshabilitar distribución primero
    echo "    Deshabilitando distribución..."
    CONFIG=$(aws cloudfront get-distribution-config --id "$DIST_ID")
    ETAG=$(echo "$CONFIG" | jq -r '.ETag')
    CONFIG_JSON=$(echo "$CONFIG" | jq '.DistributionConfig')
    CONFIG_JSON=$(echo "$CONFIG_JSON" | jq '.Enabled = false')
    
    aws cloudfront update-distribution \
      --id "$DIST_ID" \
      --distribution-config "$CONFIG_JSON" \
      --if-match "$ETAG"
    
    echo "    Esperando deshabilitación..."
    sleep 30
    
    # Eliminar distribución
    echo "    Eliminando distribución..."
    aws cloudfront delete-distribution --id "$DIST_ID" --if-match "$ETAG"
  done
  echo "✓ Distribuciones CloudFront eliminadas"
else
  echo "✓ No hay distribuciones CloudFront para eliminar"
fi

echo ""
echo "5. Verificando tablas DynamoDB..."
echo "---------------------------------"

# Verificar tablas DynamoDB
TABLES=("harrison-jobs" "harrison-idempotency")

for TABLE in "${TABLES[@]}"; do
  if aws dynamodb describe-table --table-name "$TABLE" --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "Tabla DynamoDB encontrada: $TABLE"
    
    # Eliminar tabla
    echo "  Eliminando tabla..."
    aws dynamodb delete-table --table-name "$TABLE" --region "$AWS_REGION"
    echo "  Esperando eliminación..."
    aws dynamodb wait table-not-exists --table-name "$TABLE" --region "$AWS_REGION"
    echo "✓ Tabla $TABLE eliminada"
  else
    echo "✓ No hay tabla $TABLE para eliminar"
  fi
done

echo ""
echo "6. Verificando colas SQS..."
echo "---------------------------"

# Verificar colas SQS
QUEUES=("harrison-jobs-queue" "harrison-jobs-dlq" "harrison-jobs-priority")

for QUEUE_NAME in "${QUEUES[@]}"; do
  # Obtener URL de la cola
  QUEUE_URL=$(aws sqs get-queue-url --queue-name "$QUEUE_NAME" --region "$AWS_REGION" --query 'QueueUrl' --output text 2>/dev/null || echo "")
  
  if [ -n "$QUEUE_URL" ]; then
    echo "Cola SQS encontrada: $QUEUE_NAME"
    
    # Eliminar cola
    echo "  Eliminando cola..."
    aws sqs delete-queue --queue-url "$QUEUE_URL" --region "$AWS_REGION"
    echo "✓ Cola $QUEUE_NAME eliminada"
  else
    echo "✓ No hay cola $QUEUE_NAME para eliminar"
  fi
done

echo ""
echo "7. Verificando secretos Secrets Manager..."
echo "------------------------------------------"

# Verificar secreto
if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "Secreto encontrado: $SECRET_NAME"
  
  # Eliminar secreto
  echo "  Eliminando secreto..."
  aws secretsmanager delete-secret --secret-id "$SECRET_NAME" --force-delete-without-recovery --region "$AWS_REGION"
  echo "✓ Secreto eliminado"
else
  echo "✓ No hay secreto para eliminar"
fi

echo ""
echo "8. Verificando servicios App Runner..."
echo "--------------------------------------"

# Verificar servicios App Runner
SERVICES=("harrison-api" "harrison-worker")

for SERVICE in "${SERVICES[@]}"; do
  SERVICE_ARN=$(aws apprunner list-services --region "$AWS_REGION" \
    --query "ServiceSummaryList[?ServiceName=='$SERVICE'].ServiceArn" \
    --output text 2>/dev/null || echo "")
  
  if [ -n "$SERVICE_ARN" ]; then
    echo "Servicio App Runner encontrado: $SERVICE"
    
    # Eliminar servicio
    echo "  Eliminando servicio..."
    aws apprunner delete-service --service-arn "$SERVICE_ARN" --region "$AWS_REGION"
    echo "✓ Servicio $SERVICE eliminado"
  else
    echo "✓ No hay servicio $SERVICE para eliminar"
  fi
done

echo ""
echo "9. Verificando API Gateway..."
echo "-----------------------------"

# Buscar APIs de API Gateway
APIS=$(aws apigateway get-rest-apis --region "$AWS_REGION" \
  --query "items[?contains(name, '$STACK_PREFIX')].id" \
  --output text 2>/dev/null || echo "")

if [ -n "$APIS" ]; then
  echo "APIs de API Gateway encontradas:"
  for API_ID in $APIS; do
    echo "  - $API_ID"
    
    # Eliminar API
    echo "    Eliminando API..."
    aws apigateway delete-rest-api --rest-api-id "$API_ID" --region "$AWS_REGION"
    echo "✓ API $API_ID eliminada"
  done
else
  echo "✓ No hay APIs de API Gateway para eliminar"
fi

echo ""
echo "=== Limpieza completada ==="
echo ""
echo "Recursos eliminados:"
echo "- Stacks de CloudFormation"
echo "- Repositorio ECR"
echo "- Bucket S3"
echo "- Distribuciones CloudFront"
echo "- Tablas DynamoDB"
echo "- Colas SQS"
echo "- Secretos Secrets Manager"
echo "- Servicios App Runner"
echo "- APIs de API Gateway"
echo ""
echo "Ahora puedes desplegar desde cero."