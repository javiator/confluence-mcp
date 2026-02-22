data "aws_caller_identity" "current" {}

# 1. Lambda IAM Role
resource "aws_iam_role" "lambda_role" {
  name = "ConfluenceToolsLambdaRole"
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

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "lambda_invoke_url_policy" {
  name = "LambdaInvokeUrlPolicy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "lambda:InvokeFunction",
          "lambda:InvokeFunctionUrl"
        ]
        Resource = "*" 
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_invoke_url_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_invoke_url_policy.arn
}

# 2. Package Lambda Code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_function.zip"
}

# 3. Lambda Function
resource "aws_lambda_function" "confluence_tools" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "ConfluenceTools"
  role             = aws_iam_role.lambda_role.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 30

  environment {
    variables = {
    }
  }
}

# 4. Bedrock Agent IAM Role
resource "aws_iam_role" "bedrock_agent_role" {
  name = "BedrockAgentRole_Confluence"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "bedrock_agent_policy" {
  name = "BedrockAgentPolicy_Confluence"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "bedrock:InvokeModel"
        Resource = "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
      },
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.confluence_tools.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bedrock_agent_policy_attachment" {
  role       = aws_iam_role.bedrock_agent_role.name
  policy_arn = aws_iam_policy.bedrock_agent_policy.arn
}

resource "aws_lambda_permission" "allow_bedrock" {
  statement_id  = "AllowExecutionFromBedrock"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.confluence_tools.function_name
  principal     = "bedrock.amazonaws.com"
  source_arn    = "arn:aws:bedrock:us-east-1:${data.aws_caller_identity.current.account_id}:agent/*"
}

# 5. Bedrock Agent & Action Group
resource "aws_bedrockagent_agent" "confluence_agent" {
  agent_name              = "confluence-multi-agent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model        = "anthropic.claude-3-haiku-20240307-v1:0"
  instruction             = <<EOF
You are a specialized Confluence assistant.
Your job is to help users search for, read, create, and update Confluence pages.
Coordinate with the user and use the available tools to complete their requests.
EOF
}

resource "aws_bedrockagent_agent_action_group" "confluence_actions" {
  agent_id             = aws_bedrockagent_agent.confluence_agent.id
  agent_version        = "DRAFT"
  action_group_name    = "confluence-actions"
  action_group_state   = "ENABLED"
  
  action_group_executor {
    lambda = aws_lambda_function.confluence_tools.arn
  }

  function_schema {
    member_functions {
      functions {
        name        = "search_confluence"
        description = "Search Confluence for pages using CQL"
        parameters {
          map_block_key = "query"
          type          = "string"
          description   = "The search query"
          required      = true
        }
      }
      functions {
        name        = "get_confluence_page"
        description = "Read the content of a Confluence page"
        parameters {
          map_block_key = "page_id"
          type          = "string"
          description   = "The ID of the page to read"
          required      = true
        }
      }
    }
  }
}

output "agent_id" {
  value = aws_bedrockagent_agent.confluence_agent.id
}
