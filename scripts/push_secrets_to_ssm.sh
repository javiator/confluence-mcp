#!/bin/bash
# scripts/push_secrets_to_ssm.sh
# Migrates .env secrets to AWS SSM Parameter Store

# Load .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

echo "Pushing secrets to SSM..."

aws ssm put-parameter --name "/confluence/base_url" --value "$CONFLUENCE_BASE_URL" --type "String" --overwrite
aws ssm put-parameter --name "/confluence/email" --value "$CONFLUENCE_EMAIL" --type "String" --overwrite
aws ssm put-parameter --name "/confluence/api_token" --value "$CONFLUENCE_API_TOKEN" --type "SecureString" --overwrite

echo "✅ Secrets successfully pushed to AWS SSM Parameter Store."
