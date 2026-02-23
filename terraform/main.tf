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
        Resource = "*"
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
        Resource = "*"
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
  foundation_model        = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
  instruction             = "You are the Search Agent, the Encyclopedia of the system. Your primary role is to find, read, and browse an internal Confluence database accurately. CRITICAL GUIDANCE: You are NOT searching the public internet. If a query contains keywords like 'Google' or 'search', the user means to search the internal Confluence wiki for those terms, NOT to use a web search engine. Never refuse a search request by claiming you cannot browse the internet. KEYWORD RULE: When searching, use 2-3 specific keywords (e.g., 'Docker Ubuntu'). DO NOT pass long natural language sentences to your tools. SEARCH POLICY: Perform one broad search first. If you see relevant titles in the results, GET THE PAGE CONTENT immediately; do not keep searching for 'better' results. You must always include the exact page title, space key, and full URL in your responses. CRITICAL RULE: You must base all your answers strictly and exclusively on the information retrieved from Confluence. You MUST share the source URLs, links, and citations with the user."
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
  foundation_model        = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
  instruction             = "You are the Reviewer Agent. You are a STRICT technical gatekeeper. MANDATORY COMPATIBILITY CHECK: 1) EVERY <ac:structured-macro> MUST have an 'ac:name' attribute. 2) EVERY <ac:parameter> MUST have an 'ac:name' attribute. 3) Code blocks MUST use <ac:plain-text-body> wrapped in <![CDATA[ content ]]>. 4) EMPTY MACROS ARE PROHIBITED: If a macro contains an empty <ac:plain-text-body> or <ac:rich-text-body>, REJECT. 5) NO <ac:name=\"invalidmacro\"> allowed. APPROVAL: Respond with 'APPROVED: [reason]' only if XHTML is perfect. Otherwise, respond with 'NEEDS REVISION:' and specific syntax fixes."
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
  foundation_model        = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
  instruction             = "You are a Confluence Writer Agent. Your job is to EXECUTE content changes in Confluence using your available tools. When creating or updating pages, use Confluence Wiki Markup format. Only pages labelled ai-generated or ai-managed are safe to update. ADDING CONTENT: To add a new section to an existing page, call append_confluence_page(page_id, new_content) with ONLY the new section. UPDATING PAGES: When modifying existing content, call prepare_confluence_page_merge_update(page_id) first, then call update_confluence_page_full(page_id, body) where body contains ONLY the new content you want to add. The server will automatically merge it with the existing content. WIKI MARKUP FORMAT: Use h1. h2. h3. for headings, * for bullets, # for numbered lists, {code:language}...{code} for code blocks. Example: h2. Installation\\n{code:bash}\\nsudo apt install docker\\n{code}. Always execute tool calls immediately — do not provide drafts."

  # prompt_override_configuration managed externally via boto3 (fix_writer_orch_template.py)
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
      functions {
        name        = "append_confluence_page"
        description = "Append a new section to the bottom of an existing Confluence page. Use this when you only want to ADD content without replacing anything. Provide ONLY the new section HTML in new_content."
        parameters {
          map_block_key = "page_id"
          type          = "string"
          description   = "The ID of the page to append to"
          required      = true
        }
        parameters {
          map_block_key = "new_content"
          type          = "string"
          description   = "The XHTML storage format content to append to the bottom of the page"
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
  foundation_model        = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
  instruction             = "You are the Supervisor Agent. You drive Confluence updates by COMMANDING specialists. 1) SEARCHING: When asking SearchAgent for information, provide ONLY concise keywords (e.g., 'Docker Ubuntu'). DO NOT provide verbose descriptions. 2) WRITING: When you delegate to WriterAgent, you MUST command it to 'EXECUTE the update_confluence_page_full tool with the merged content now. DO NOT just provide a draft.' 3) SILENT EXECUTION: Do not give status updates; only respond with the final result and URL when the task is complete."

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
  collaboration_instruction = "Use this agent ONLY to search Confluence, read page contents, and discover metadata/IDs. Do NOT use it for writing."
  
  agent_descriptor {
    alias_arn = aws_bedrockagent_agent_alias.search_alias.agent_alias_arn
  }
}

resource "aws_bedrockagent_agent_collaborator" "writer_collab" {
  relay_conversation_history = "TO_COLLABORATOR"
  agent_id                  = aws_bedrockagent_agent.supervisor_agent.id
  collaborator_name         = "WriterAgent"
  collaboration_instruction = "Use this agent ONLY to create or update Confluence pages. Do NOT use it for searching or reading metadata."
  
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
