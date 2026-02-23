#!/bin/bash
set -e

AGENTS=("HMUJPTSXHZ" "M1SKX5WXKI" "CEXKSDYGIG" "WRRZLA5LTA")
ALIAS_IDS=("LRCPLKP7QR" "XN7Q0IVSHR" "XVRG1JV6YW" "TSTALIASID")
NAMES=("search-alias" "writer-alias" "reviewer-alias" "AgentTestAlias")

for i in "${!AGENTS[@]}"; do
  AGENT_ID="${AGENTS[$i]}"
  ALIAS_ID="${ALIAS_IDS[$i]}"
  ALIAS_NAME="${NAMES[$i]}"
  
  echo "--- Processing Agent: $AGENT_ID ---"
  
  # Prepare Agent
  echo "Preparing agent..."
  aws bedrock-agent prepare-agent --agent-id "$AGENT_ID" --region us-east-1 > /dev/null
  
  # Wait for preparation
  echo "Waiting for preparation..."
  while true; do
    STATUS=$(aws bedrock-agent get-agent --agent-id "$AGENT_ID" --region us-east-1 --query 'agent.agentStatus' --output text)
    if [ "$STATUS" == "PREPARED" ]; then
      break
    fi
    sleep 2
  done
  
  # Create Version
  echo "Creating version..."
  VERSION=$(aws bedrock-agent create-agent-version --agent-id "$AGENT_ID" --region us-east-1 --query 'agentVersion.version' --output text)
  echo "New Version: $VERSION"
  
  # Update Alias
  echo "Updating alias $ALIAS_ID ($ALIAS_NAME) to version $VERSION..."
  aws bedrock-agent update-agent-alias --agent-id "$AGENT_ID" --agent-alias-id "$ALIAS_ID" --agent-alias-name "$ALIAS_NAME" --routing-configuration "[{\"agentVersion\": \"$VERSION\"}]" --region us-east-1 > /dev/null
done

echo "--- ALL AGENTS UPDATED ---"
