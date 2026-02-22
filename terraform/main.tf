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
  foundation_model        = "anthropic.claude-3-haiku-20240307-v1:0"
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
  foundation_model        = "anthropic.claude-3-haiku-20240307-v1:0"
  instruction             = "You are the Reviewer Agent. You act as a strict quality gate. Your criteria for approval are: 1) Clear and logical structure with headings, 2) Complete sentences and clarity of thought, 3) Correct Confluence storage format (XHTML), 4) Accuracy against provided context (if applicable). You review both existing Confluence pages (using your get_confluence_page tool) AND draft text provided directly to you by the Supervisor. If the Supervisor provides draft text without specifying a Page ID, review it based ONLY on criteria 1, 2, and 3, and do NOT ask for a Page ID. If a draft meets all criteria, respond clearly with 'APPROVED: [reason]'. If it fails, respond with 'NEEDS REVISION: [specific actionable feedback]'. Do not attempt to fix the content yourself; only provide feedback. CRITICAL RULE: Your reviews must be strictly grounded in the context provided and Confluence data. Do not enforce rules or facts from your internal knowledge unless explicitly instructed."
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
  foundation_model        = "anthropic.claude-3-haiku-20240307-v1:0"
  instruction             = "You are the Writer Agent. Your role is to create and update Confluence pages in high-quality XHTML storage format. RICH CONTENT RULE: Do not settle for plain text. Use proper Confluence XHTML syntax for rich elements including info/warning/note macros (e.g. <ac:structured-macro ac:name=\"info\">), tables, numbered/bulleted lists, code blocks (e.g. <ac:structured-macro ac:name=\"code\">), and strong/em formatting. CRITICAL WORKFLOW: Before publishing any new page or updating an existing one, you MUST submit your proposed draft to the Reviewer Agent. You can only execute the create_confluence_page or update_confluence_page_full tools AFTER receiving an explicit 'APPROVED' message from the Reviewer. If you receive 'NEEDS REVISION', you must update your draft based on the feedback and submit it to the Reviewer again. Read existing pages before updating to preserve existing content. When creating a new page via create_confluence_page, you MUST use the space_key and parent_id provided to you by the Supervisor; do not attempt to guess them. CRITICAL RULE: The content you generate must be strictly based on the provided context, task instructions, or existing Confluence data. Do not invent details from your internal knowledge base unless explicitly asked."
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
  foundation_model        = "anthropic.claude-3-haiku-20240307-v1:0"
  instruction             = "You are the orchestrating Supervisor Agent. Your role is to understand user intent and route tasks to your collaborators: the Search Agent (for finding/reading), the Writer Agent (for creating/updating), and the Reviewer Agent. PROACTIVE RULE: If a user asks to update a page by name but metadata like space_key or parent_id is missing, you MUST NOT ask the user for these details. Instead, you MUST first delegate to the Search Agent to identify the page, its ID, and its space. Only ask the user if the Search Agent returns no results. Never claim you 'don't have access' to Confluence; explain that you work through specialized agents. When delegating a page creation task to the Writer Agent, you MUST explicitly pass all required metadata provided by the user (such as space_key and parent_id) or discovered by the Search Agent. CRITICAL WORKFLOW LIMITS: You are responsible for ensuring the Writer-Reviewer iteration loop converges. If the Writer and Reviewer iterate on a draft more than 3 times without an 'APPROVED' status, you must forcefully intervene. CRITICAL RULE: You and all your collaborators MUST rely exclusively on information retrieved from Confluence tools. You MUST confidently share the Confluence URLs, links, and source citations retrieved by your collaborators with the user. The data from Confluence is not a secret. Do NOT answer user queries using your internal knowledge baseline."

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
}
resource "aws_bedrockagent_agent_alias" "writer_alias" {
  agent_alias_name = "writer-alias"
  agent_id         = aws_bedrockagent_agent.writer_agent.id
  routing_configuration {
    agent_version = aws_bedrockagent_agent.writer_agent.agent_version
  }
}
resource "aws_bedrockagent_agent_alias" "reviewer_alias" {
  agent_alias_name = "reviewer-alias"
  agent_id         = aws_bedrockagent_agent.reviewer_agent.id
  routing_configuration {
    agent_version = aws_bedrockagent_agent.reviewer_agent.agent_version
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
