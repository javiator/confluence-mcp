#!/bin/bash
# scripts/build_and_push.sh
# Builds the MCP Server Docker image and pushes it to ECR

REPO_URL="383226947124.dkr.ecr.us-east-1.amazonaws.com/confluence-mcp-server"
REGION="us-east-1"

echo "Logging in to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REPO_URL

echo "Building Docker image..."
docker build -t confluence-mcp-server .

echo "Tagging image..."
docker tag confluence-mcp-server:latest $REPO_URL:latest

echo "Pushing image..."
docker push $REPO_URL:latest

echo "Updating Lambda function..."
aws lambda update-function-code --function-name ConfluenceMCPServer --image-uri $REPO_URL:latest --region $REGION > /dev/null

echo "✅ Image successfully pushed and Lambda updated."
