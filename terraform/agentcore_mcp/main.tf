# AgentCore MCP Server — dedicated Lambda for the single-agent AgentCore setup.
#
# This module is COMPLETELY SEPARATE from terraform/managed/ which contains
# ConfluenceMCPServer and ConfluenceTools used by the legacy 4-agent Bedrock
# Agents system.  Nothing here touches those resources.

data "aws_caller_identity" "current" {}

# ── ECR Repository ────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "agentcore_mcp" {
  name                 = "confluence-agentcore-mcp"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ── IAM Role ─────────────────────────────────────────────────────────────────

resource "aws_iam_role" "agentcore_mcp_role" {
  name = "ConfluenceAgentCoreMCPRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "agentcore_mcp_basic" {
  role       = aws_iam_role.agentcore_mcp_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# SSM read access — same parameters used by ConfluenceMCPServer so we reference
# their ARNs without modifying the originals.
resource "aws_iam_policy" "agentcore_mcp_ssm" {
  name = "AgentCoreMCPSSMPolicy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ssm:GetParameter", "ssm:GetParameters"]
        # Reference the same SSM params already created in terraform/managed/mcp_server.tf
        Resource = [
          "arn:aws:ssm:us-east-1:${data.aws_caller_identity.current.account_id}:parameter/confluence/base_url",
          "arn:aws:ssm:us-east-1:${data.aws_caller_identity.current.account_id}:parameter/confluence/email",
          "arn:aws:ssm:us-east-1:${data.aws_caller_identity.current.account_id}:parameter/confluence/api_token"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "agentcore_mcp_ssm_attach" {
  role       = aws_iam_role.agentcore_mcp_role.name
  policy_arn = aws_iam_policy.agentcore_mcp_ssm.arn
}

# ── Lambda Function ───────────────────────────────────────────────────────────

resource "aws_lambda_function" "agentcore_mcp" {
  function_name = "ConfluenceAgentCoreMCP"
  role          = aws_iam_role.agentcore_mcp_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.agentcore_mcp.repository_url}:latest"
  timeout       = 120
  memory_size   = 512
  architectures = ["arm64"]

  environment {
    variables = {
      AWS_LAMBDA_WEB_ADAPTER_ENABLER = "true"
    }
  }

  lifecycle {
    ignore_changes = [image_uri]
  }
}

# ── Function URL (IAM auth) ───────────────────────────────────────────────────

resource "aws_lambda_function_url" "agentcore_mcp_url" {
  function_name      = aws_lambda_function.agentcore_mcp.function_name
  authorization_type = "AWS_IAM"
}

# ── Allow AgentCore Gateway to invoke this Function URL ───────────────────────

resource "aws_lambda_permission" "allow_agentcore_gateway" {
  statement_id           = "AllowAgentCoreGatewayInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.agentcore_mcp.function_name
  principal              = "bedrock-agentcore.amazonaws.com"
  function_url_auth_type = "AWS_IAM"
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "agentcore_mcp_ecr_url" {
  description = "ECR repository URL — use this in build-and-push commands"
  value       = aws_ecr_repository.agentcore_mcp.repository_url
}

output "agentcore_mcp_function_url" {
  description = "Lambda Function URL — use this as the AgentCore Gateway endpoint (append /mcp)"
  value       = aws_lambda_function_url.agentcore_mcp_url.function_url
}

output "agentcore_mcp_lambda_arn" {
  description = "Lambda ARN — needed for the IAM Gateway role policy"
  value       = aws_lambda_function.agentcore_mcp.arn
}
