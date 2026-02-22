# Phase 4.3: Bedrock Multi-Agent System (MAS)

This guide documents the implementation of the Multi-Agent System using AWS Bedrock Agents.

## 1. Architecture Overview

The system follows a **Supervisor-Collaborator** pattern:

*   **Supervisor Agent**: Orchestrates tasks and delegates to specialists.
*   **Search Agent**: Discovers and reads Confluence content.
*   **Writer Agent**: Creates and updates pages with safe formatting defaults.
*   **Reviewer Agent**: Acts as a technical gatekeeper for XHTML compatibility.

## 2. Rendering & Formatting Strategy

To solve the "Error loading the extension!" issues, the system now enforces a **Standard-First** approach:

### Safe Formatting Defaults
The Writer Agent is instructed to use standard HTML elements whenever possible:
*   `<p>`, `<ul>`, `<li>`, `<ol>`
*   `<h1>` through `<h4>`
*   `<strong>`, `<em>`
*   `<table>`
*   `<code>` (for inline or simple blocks)

### Rich Formatting (Macros)
Confluence macros (`info`, `note`, `code`) are used **only** when specifically requested or for high-impact content.

## 3. Robust XHTML Sanitation

The MCP server includes a server-side `robust_sanitize_confluence_xhtml` function that:
1.  **Strips Zombie Macros**: Removes any `invalidmacro` tags left by failed Confluence rendering.
2.  **Repairs Missing Attributes**: Automatically adds `ac:name` and `ac:parameter` names if the LLM forgets them.
3.  **Preserves CDATA**: Uses targeted regex instead of HTML parsers to ensure code blocks remain intact.

## 4. Verification Flow

1.  **Retrieve**: Always use `prepare_confluence_page_merge_update` to get clean base content.
2.  **Verify**: The Reviewer Agent uses a technical checklist to approve/reject the draft.
3.  **Publish**: Only APPROVED content is submitted to the Confluence API.
