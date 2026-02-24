#!/bin/bash
set -e

# New Deploy Script for AgentCore Runtime Agent
# usage: ./deploy_agent.sh [simple|main]

TARGET=${1:-main}
S3_BUCKET="bedrock-agentcore-runtime-383226947124-us-east-1-vv5aiw1cye"
S3_PREFIX="confluence_agent"

case $TARGET in
  minimal)
    ENTRY_FILE="main_minimal.py"
    ZIP_NAME="agent_minimal.zip"
    REQ_FILE="requirements_minimal.txt"
    ;;
  simple)
    ENTRY_FILE="main_simple.py"
    ZIP_NAME="agent_simple.zip"
    REQ_FILE="requirements.txt"
    ;;
  main)
    ENTRY_FILE="main.py"
    ZIP_NAME="agent.zip"
    REQ_FILE="requirements.txt"
    ;;
  ultra_minimal)
    ENTRY_FILE="main_ultra_minimal.py"
    ZIP_NAME="agent_ultra_minimal.zip"
    REQ_FILE="requirements_ultra_minimal.txt"
    ;;
  diagnostic)
    ENTRY_FILE="main_diagnostic.py"
    ZIP_NAME="agent_diagnostic.zip"
    REQ_FILE="requirements_diagnostic.txt"
    ;;
  *)
    echo "Usage: $0 [simple|main]"
    exit 1
    ;;
esac

echo "Packaging agent ($TARGET)..."
# Create a temporary directory for packaging to avoid including venv/test files
TEMP_DIR=$(mktemp -d)
cp "$ENTRY_FILE" "$TEMP_DIR/main.py"  # Always rename to main.py for consistent AgentCore entry point
cp "$REQ_FILE" "$TEMP_DIR/requirements.txt"

cd "$TEMP_DIR"
echo "Contents before pip install:"
ls -F
echo "Installing dependencies into package..."
python3 -m pip install -r requirements.txt -t . --quiet
echo "Contents after pip install (file count):"
find . -type f | wc -l

echo "Creating zip..."
python3 -c "import zipfile, os; z = zipfile.ZipFile('$ZIP_NAME', 'w', zipfile.ZIP_DEFLATED); [z.write(os.path.join(root, f), os.path.relpath(os.path.join(root, f), '.')) for root, dirs, files in os.walk('.') for f in files if f != '$ZIP_NAME']; z.close()"
cd - > /dev/null

mv "$TEMP_DIR/$ZIP_NAME" .
rm -rf "$TEMP_DIR"

echo "Uploading to S3..."
aws s3 cp "$ZIP_NAME" "s3://${S3_BUCKET}/${S3_PREFIX}/${ZIP_NAME}"

echo "✅ Agent deployed to s3://${S3_BUCKET}/${S3_PREFIX}/${ZIP_NAME}"
echo ""
echo "Next steps in AWS Console (Bedrock → AgentCore → Host agent or tool):"
echo "1. Source: S3 bucket"
echo "2. URL: s3://${S3_BUCKET}/${S3_PREFIX}/${ZIP_NAME}"
echo "3. Entry point: main.py"
echo "4. Handler: invoke (via @app.entrypoint)"
