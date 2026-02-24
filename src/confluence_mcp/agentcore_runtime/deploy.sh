#!/bin/bash
set -e

# Deploy AgentCore Runtime agent to S3

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S3_BUCKET="bedrock-agentcore-runtime-383226947124-us-east-1-vv5aiw1cye"
S3_PREFIX="confluence_agent"

echo "Packaging agent..."
cd "$SCRIPT_DIR"
zip -r agent.zip main.py requirements.txt

echo "Uploading to S3..."
aws s3 cp agent.zip "s3://${S3_BUCKET}/${S3_PREFIX}/agent.zip"

echo "✅ Agent deployed to s3://${S3_BUCKET}/${S3_PREFIX}/agent.zip"
echo ""
echo "Next steps:"
echo "1. Go to AWS Console → Bedrock → AgentCore → Host agent or tool"
echo "2. Choose S3 bucket: ${S3_BUCKET}"
echo "3. S3 key: ${S3_PREFIX}/agent.zip"
echo "4. Entry point: main.py"
echo "5. Handler function: handler"
