#!/bin/bash
# scripts/deploy_agentcore_mcp.sh
# Automates building and pushing the AgentCore MCP server image to ECR
# and updating the ConfluenceAgentCoreMCP Lambda function.

set -e

REGION="us-east-1"
TF_DIR="terraform/agentcore_mcp"
DOCKERFILE="Dockerfile.agentcore"
IMAGE_NAME="confluence-agentcore-mcp"
FUNCTION_NAME="ConfluenceAgentCoreMCP"

# Get the script directory to handle relative paths correctly
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "🔍 Fetching ECR URL from Terraform..."
ECR_URL=$(terraform -chdir="$TF_DIR" output -raw agentcore_mcp_ecr_url)

if [ -z "$ECR_URL" ]; then
    echo "❌ Error: Could not retrieve ECR URL. Ensure terraform has been initialized and applied in $TF_DIR"
    exit 1
fi

echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_URL"

echo "🏗️  Building Docker image using $DOCKERFILE..."
docker build -f "$DOCKERFILE" -t "$IMAGE_NAME" .

echo "🏷️  Tagging image..."
docker tag "$IMAGE_NAME:latest" "$ECR_URL:latest"

echo "🚀 Pushing image to ECR..."
docker push "$ECR_URL:latest"

echo "⚡ Updating Lambda function $FUNCTION_NAME..."
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --image-uri "$ECR_URL:latest" \
    --region "$REGION" > /dev/null

echo "⏳ Waiting for Lambda update to complete..."
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

echo "✅ Deployment successful!"
echo "💡 You can now run: agentcore invoke '{\"prompt\": \"Search for google ai products\"}'"
