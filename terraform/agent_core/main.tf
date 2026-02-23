data "aws_caller_identity" "current" {}

# IAM Role for Bedrock Runtime access
resource "aws_iam_role" "agent_core_role" {
  name = "AgentCoreRuntimeRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com" # Or ecs-tasks.amazonaws.com
        }
      }
    ]
  })
}

# Minimal policy for Bedrock Converse API
resource "aws_iam_policy" "bedrock_runtime_policy" {
  name = "BedrockRuntimeCorePolicy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*" # Restrict to specific Claude models in production
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bedrock_runtime_attach" {
  role       = aws_iam_role.agent_core_role.name
  policy_arn = aws_iam_policy.bedrock_runtime_policy.arn
}

output "agent_core_role_arn" {
  value = aws_iam_role.agent_core_role.arn
}
