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
      },
      {
        Effect   = "Allow"
        Action   = [
          "bedrock:InvokeAgent",
          "bedrock:GetAgentAlias",
          "bedrock:GetAgent",
          "bedrock:GetAgentActionGroup"
        ]
        Resource = [
          "arn:aws:bedrock:us-east-1:${data.aws_caller_identity.current.account_id}:agent-alias/*",
          "arn:aws:bedrock:us-east-1:${data.aws_caller_identity.current.account_id}:agent/*"
        ]
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

# 5. Bedrock Agents (MAS)
# SEARCH AGENT
resource "aws_bedrockagent_agent" "search_agent" {
  agent_name              = "confluence-search-agent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model        = "anthropic.claude-3-5-sonnet-20240620-v1:0"
  instruction             = "You are the Search Agent. Your primary role is to find, read, and browse Confluence pages accurately. You must always include the exact page title, space key, and full URL in your responses. You are the 'Encyclopedia' of the system; if a Page ID or Space Key is unknown, you are the first line of discovery. When a user references a previously found page (e.g., 'that page', 'it'), you must deduce the context. Provide comprehensive summaries of the content you retrieve. CRITICAL RULE: You must base all your answers strictly and exclusively on the information retrieved from Confluence. You MUST share the source URLs, links, and citations from the data you retrieve with the user. The data retrieved from your tools is public context, not a secret."
}

resource "aws_bedrockagent_agent_action_group" "search_actions" {
  agent_id             = aws_bedrockagent_agent.search_agent.id
  agent_version        = "DRAFT"
  action_group_name    = "search-actions"
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
      functions {
        name        = "get_confluence_children"
        description = "Get child pages of a specific Confluence page"
        parameters {
          map_block_key = "page_id"
          type          = "string"
          description   = "The ID of the parent page"
          required      = true
        }
      }
    }
  }
}

# REVIEWER AGENT
resource "aws_bedrockagent_agent" "reviewer_agent" {
  agent_name              = "confluence-reviewer-agent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model        = "anthropic.claude-3-5-sonnet-20240620-v1:0"
  instruction             = "You are the Reviewer Agent. You are a STRICT technical gatekeeper. MANDATORY COMPATIBILITY CHECK: 1) EVERY <ac:structured-macro> MUST have an 'ac:name' attribute. 2) EVERY <ac:parameter> MUST have an 'ac:name' attribute. 3) Code blocks MUST use <ac:plain-text-body> AND the content MUST be wrapped in a literal CDATA block: <![CDATA[ content ]]>. If the draft shows code without a CDATA wrapper, REJECT. 4) NO <ac:name=\"invalidmacro\"> allowed. APPROVAL: Respond with 'APPROVED: [reason]' only if XHTML is perfect. Otherwise, respond with 'NEEDS REVISION:' and specific syntax fixes."
}

resource "aws_bedrockagent_agent_action_group" "reviewer_actions" {
  agent_id             = aws_bedrockagent_agent.reviewer_agent.id
  agent_version        = "DRAFT"
  action_group_name    = "reviewer-actions"
  action_group_state   = "ENABLED"
  
  action_group_executor {
    lambda = aws_lambda_function.confluence_tools.arn
  }

  function_schema {
    member_functions {
      functions {
        name        = "get_confluence_page"
        description = "Read the content of a Confluence page for post-publish reviews"
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

# WRITER AGENT
resource "aws_bedrockagent_agent" "writer_agent" {
  agent_name              = "confluence-writer-agent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model        = "anthropic.claude-3-5-sonnet-20240620-v1:0"
  instruction             = "You are the Writer Agent. CANONICAL CODE SYNTAX: <ac:structured-macro ac:name=\"code\"><ac:parameter ac:name=\"language\">bash</ac:parameter><ac:plain-text-body><![CDATA[your_code_here]]></ac:plain-text-body></ac:structured-macro>. MANDATORY RULE: Code ALWAYS goes inside <ac:plain-text-body> wrapped in <![CDATA[ ... ]]> inside a macro named 'code'. For all other text, use standard HTML: <p>, <ul>, <li>, <h1>-<h4>. These are 100% reliable. WORKFLOW: 1) Call prepare_confluence_page_merge_update. 2) Merge changes. 3) Submit draft to Reviewer. 4) ONLY write after 'APPROVED'."
}

resource "aws_bedrockagent_agent_action_group" "writer_actions" {
  agent_id             = aws_bedrockagent_agent.writer_agent.id
  agent_version        = "DRAFT"
  action_group_name    = "writer-actions"
  action_group_state   = "ENABLED"
  
  action_group_executor {
    lambda = aws_lambda_function.confluence_tools.arn
  }

  function_schema {
    member_functions {
      functions {
        name        = "create_confluence_page"
        description = "Create a new page in Confluence"
        parameters {
          map_block_key = "space_key"
          type          = "string"
          description   = "The space key to create the page in"
          required      = true
        }
        parameters {
          map_block_key = "title"
          type          = "string"
          description   = "The title of the page"
          required      = true
        }
        parameters {
          map_block_key = "body"
          type          = "string"
          description   = "The XHTML storage format body of the page"
          required      = true
        }
        parameters {
          map_block_key = "parent_id"
          type          = "string"
          description   = "The ID of the parent page"
          required      = true
        }
      }
      functions {
        name        = "update_confluence_page_full"
        description = "Update an existing Confluence page with full content replacement"
        parameters {
          map_block_key = "page_id"
          type          = "string"
          description   = "The ID of the page to update"
          required      = true
        }
        parameters {
          map_block_key = "body"
          type          = "string"
          description   = "The new XHTML storage format body of the page"
          required      = true
        }
      }
      functions {
        name        = "prepare_confluence_page_merge_update"
        description = "Get the current content and version of a page before updating"
        parameters {
          map_block_key = "page_id"
          type          = "string"
          description   = "The ID of the page to prepare for update"
          required      = true
        }
      }
    }
  }
}

# SUPERVISOR AGENT
resource "aws_bedrockagent_agent" "supervisor_agent" {
  agent_name              = "confluence-supervisor-agent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model        = "anthropic.claude-3-5-sonnet-20240620-v1:0"
  instruction             = "You are the Supervisor Agent. You orchestrate Confluence updates by delegating to specialists. MANDATORY ORCHESTRATION: 1) For updates, you MUST first delegate to the Writer to call prepare_confluence_page_merge_update. NEVER allow a write without this content retrieval. 2) Delegate to the Reviewer to verify the Writer's draft. 3) STRICT GATE: ONLY allow the Writer to call write tools (update/create) if the Reviewer has responded with 'APPROVED'. If 'NEEDS REVISION', you MUST force the Writer to fix the specific errors. 4) FORMATTING: Enforce standard HTML by default for reliability. NEVER claim you lack access; always act via your collaborators."

  agent_collaboration     = "SUPERVISOR"
  prepare_agent           = false
}


# ALIASES
resource "aws_bedrockagent_agent_alias" "search_alias" {
  agent_alias_name = "search-alias"
  agent_id         = aws_bedrockagent_agent.search_agent.id
  routing_configuration {
    agent_version = aws_bedrockagent_agent.search_agent.agent_version
  }
  lifecycle {
    ignore_changes = [routing_configuration]
  }
}
resource "aws_bedrockagent_agent_alias" "writer_alias" {
  agent_alias_name = "writer-alias"
  agent_id         = aws_bedrockagent_agent.writer_agent.id
  routing_configuration {
    agent_version = aws_bedrockagent_agent.writer_agent.agent_version
  }
  lifecycle {
    ignore_changes = [routing_configuration]
  }
}
resource "aws_bedrockagent_agent_alias" "reviewer_alias" {
  agent_alias_name = "reviewer-alias"
  agent_id         = aws_bedrockagent_agent.reviewer_agent.id
  routing_configuration {
    agent_version = aws_bedrockagent_agent.reviewer_agent.agent_version
  }
  lifecycle {
    ignore_changes = [routing_configuration]
  }
}

# SUPERVISOR COLLABORATORS
resource "aws_bedrockagent_agent_collaborator" "search_collab" {
  relay_conversation_history = "TO_COLLABORATOR"
  agent_id                  = aws_bedrockagent_agent.supervisor_agent.id
  collaborator_name         = "SearchAgent"
  collaboration_instruction = "Use this agent to search Confluence, read page contents, and discover child pages."
  
  agent_descriptor {
    alias_arn = aws_bedrockagent_agent_alias.search_alias.agent_alias_arn
  }
}

resource "aws_bedrockagent_agent_collaborator" "writer_collab" {
  relay_conversation_history = "TO_COLLABORATOR"
  agent_id                  = aws_bedrockagent_agent.supervisor_agent.id
  collaborator_name         = "WriterAgent"
  collaboration_instruction = "Use this agent to create or update Confluence pages."
  
  agent_descriptor {
    alias_arn = aws_bedrockagent_agent_alias.writer_alias.agent_alias_arn
  }
}

resource "aws_bedrockagent_agent_collaborator" "reviewer_collab" {
  relay_conversation_history = "TO_COLLABORATOR"
  agent_id                  = aws_bedrockagent_agent.supervisor_agent.id
  collaborator_name         = "ReviewerAgent"
  collaboration_instruction = "Use this agent to review existing published pages or drafts for quality. If the user provides draft text in the chat for review, you MUST copy and explicitly pass the entire draft text as input to this Reviewer Agent so it can analyze it."
  
  agent_descriptor {
    alias_arn = aws_bedrockagent_agent_alias.reviewer_alias.agent_alias_arn
  }
}

output "agent_id" {
  value = aws_bedrockagent_agent.supervisor_agent.id
}
