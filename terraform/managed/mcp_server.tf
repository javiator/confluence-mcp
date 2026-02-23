# SSM Parameters for Confluence Credentials
resource "aws_ssm_parameter" "confluence_base_url" {
  name  = "/confluence/base_url"
  type  = "String"
  value = "REPLACE_ME" # User will update this via CLI or Console
  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "confluence_email" {
  name  = "/confluence/email"
  type  = "String"
  value = "REPLACE_ME"
  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "confluence_api_token" {
  name  = "/confluence/api_token"
  type  = "SecureString"
  value = "REPLACE_ME"
  lifecycle {
    ignore_changes = [value]
  }
}

# ECR Repository for the MCP Server
resource "aws_ecr_repository" "mcp_server" {
  name                 = "confluence-mcp-server"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# IAM Role for the MCP Server Lambda
resource "aws_iam_role" "mcp_server_role" {
  name = "ConfluenceMCPServerRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "mcp_server_basic_execution" {
  role       = aws_iam_role.mcp_server_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "mcp_server_ssm_policy" {
  name = "MCPServerSSMPolicy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          aws_ssm_parameter.confluence_base_url.arn,
          aws_ssm_parameter.confluence_email.arn,
          aws_ssm_parameter.confluence_api_token.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "mcp_server_ssm_attachment" {
  role       = aws_iam_role.mcp_server_role.name
  policy_arn = aws_iam_policy.mcp_server_ssm_policy.arn
}

# Lambda Function for the MCP Server (will be updated once the image is pushed)
resource "aws_lambda_function" "mcp_server" {
  function_name = "ConfluenceMCPServer"
  role          = aws_iam_role.mcp_server_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.mcp_server.repository_url}:latest"
  timeout       = 60
  memory_size   = 512
  architectures = ["arm64"]

  environment {
    variables = {
      # Use SSM paths as identifiers if we wanted to fetch them explicitly,
      # but our server.py is coded to look at these specific paths.
      AWS_LAMBDA_WEB_ADAPTER_ENABLER = "true"
    }
  }

  lifecycle {
    ignore_changes = [image_uri]
  }
}

# Lambda Function URL with IAM Auth
resource "aws_lambda_function_url" "mcp_server_url" {
  function_name      = aws_lambda_function.mcp_server.function_name
  authorization_type = "AWS_IAM"
}

# Allow the Action Group Lambda to invoke this Function URL
resource "aws_lambda_permission" "allow_action_group_to_call_mcp" {
  statement_id  = "AllowInvokeFunctionUrl"
  action        = "lambda:InvokeFunctionUrl"
  function_name = aws_lambda_function.mcp_server.function_name
  principal     = "lambda.amazonaws.com"
  source_arn    = aws_lambda_function.confluence_tools.arn
  function_url_auth_type = "AWS_IAM"
}

output "mcp_server_repository_url" {
  value = aws_ecr_repository.mcp_server.repository_url
}

output "mcp_server_function_url" {
  value = aws_lambda_function_url.mcp_server_url.function_url
}
