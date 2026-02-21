import os
import asyncio
from typing import Dict, Any, List
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model

from crewai import Agent, Task, Crew, Process
from confluence_mcp.agent.client import MCPClient
from confluence_mcp.agent.llm import get_llm

SEARCH_TOOLS  = {"search_confluence", "get_confluence_page", "get_confluence_children"}
WRITER_TOOLS  = {"create_confluence_page", "prepare_confluence_page_merge_update",
                 "update_confluence_page_full"}
REVIEWER_TOOLS = {"get_confluence_page"}

def create_crewai_tools(mcp_client: MCPClient, allowed_tools: set, loop: asyncio.AbstractEventLoop = None):
    """
    Wrap MCP tools into LangChain StructuredTools which CrewAI can use.
    Since mcp_client.call_tool is async and CrewAI has partial async support, 
    we must wrap them properly.
    """
    crew_tools = []
    
    mcp_tools = {t.name: t for t in mcp_client.get_tools() if t.name in allowed_tools}
    
    from crewai.tools import BaseTool
 
    for name, t in mcp_tools.items():
        # Determine schema from MCP inputSchema
        def create_sync_wrapper(tool_name=name):
            def sync_run(**kwargs):
                # CrewAI kickoff runs in a separate thread via cl.make_async.
                # The MCPClient session is bound to the main Chainlit loop.
                # We must use run_coroutine_threadsafe to execute the tool call on the main loop.
                if loop and loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        mcp_client.call_tool(tool_name, kwargs), 
                        loop
                    )
                    return future.result()
                
                # Fallback for cases where loop isn't provided or running
                return asyncio.run(mcp_client.call_tool(tool_name, kwargs))
            return sync_run

        # Determine the wrapper function for this tool
        wrapper = create_sync_wrapper(name)

        from crewai.tools import BaseTool
        from pydantic import BaseModel, Field, create_model

        # Helper to convert JSON Schema to Pydantic Model (Simplified)
        def json_schema_to_pydantic(schema_dict, model_name):
            properties = schema_dict.get("properties", {})
            required = schema_dict.get("required", [])
            
            fields = {}
            for prop_name, prop_info in properties.items():
                prop_type = Any # Default
                # Basic type mapping
                json_type = prop_info.get("type")
                if json_type == "string": prop_type = str
                elif json_type == "integer": prop_type = int
                elif json_type == "boolean": prop_type = bool
                
                default = ... if prop_name in required else None
                fields[prop_name] = (prop_type, Field(default=default, description=prop_info.get("description", "")))
            
            return create_model(model_name, **fields)

        args_model = json_schema_to_pydantic(t.inputSchema, f"{name}Schema")

        def create_mcp_tool_instance(tool_name, tool_desc, run_func, schema_model):
            class MCPCustomTool(BaseTool):
                name: str = tool_name
                description: str = tool_desc
                args_schema: Any = schema_model
                
                def _run(self, **kwargs) -> Any:
                    return run_func(**kwargs)
            
            return MCPCustomTool()

        crew_tools.append(create_mcp_tool_instance(name, t.description, wrapper, args_model))
        
    return crew_tools


def create_confluence_crew(mcp_client: MCPClient, provider: str = "openai", model: str = None, loop: asyncio.AbstractEventLoop = None) -> Crew:
    """
    Create a CrewAI orchestrator for Confluence
    """
    # CrewAI (via LiteLLM) often works better with string model identifiers
    if provider == "openai":
        llm_identifier = model or "gpt-4o"
    elif provider == "anthropic":
        llm_identifier = f"anthropic/{model or 'claude-3-5-sonnet-20240620'}"
    elif provider == "google":
        # Ensure we use the correct LiteLLM prefix for Gemini
        clean_model = model or "gemini-1.5-flash"
        if clean_model.startswith("models/"):
            clean_model = clean_model.replace("models/", "")
        llm_identifier = f"gemini/{clean_model}"
    elif provider == "ollama":
        # For Ollama, we use the LangChain object directly as LiteLLM's 
        # environment-based routing can be brittle with local endpoints.
        llm_identifier = get_llm(provider, model)
    else:
        # Fallback to langchain object if unknown
        llm_identifier = get_llm(provider, model)
    
    search_tools = create_crewai_tools(mcp_client, SEARCH_TOOLS, loop=loop)
    writer_tools = create_crewai_tools(mcp_client, WRITER_TOOLS, loop=loop)
    reviewer_tools = create_crewai_tools(mcp_client, REVIEWER_TOOLS, loop=loop)

    # 1. Define Agents
    search_agent = Agent(
        role='Confluence Search Specialist',
        goal='Find the most relevant Confluence pages',
        backstory='Expert in information retrieval and CQL queries. Always provides page titles and URLs.',
        tools=search_tools,
        llm=llm_identifier,
        verbose=True
    )

    writer_agent = Agent(
        role='Confluence Technical Writer',
        goal='Create clear, well-structured documentation',
        backstory='Senior technical writer skilled at XHTML formatting and merging updates securely.',
        tools=writer_tools,
        llm=llm_identifier,
        verbose=True
    )

    reviewer_agent = Agent(
        role='Confluence Content Reviewer',
        goal='Ensure documentation meets quality standards before publishing',
        backstory='Meticulous reviewer who catches structural, factual, and formatting issues. Does pre-publish QA.',
        tools=reviewer_tools,
        llm=llm_identifier,
        verbose=True
    )

    # Note: the specific execution Tasks must be defined at runtime per user request.
    # This factory just returns the agents for now, or a default crew setup.
    return {
        "search_agent": search_agent,
        "writer_agent": writer_agent,
        "reviewer_agent": reviewer_agent,
        "llm": llm_identifier
    }
