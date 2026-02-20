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

def create_crewai_tools(mcp_client: MCPClient, allowed_tools: set):
    """
    Wrap MCP tools into LangChain StructuredTools which CrewAI can use.
    Since mcp_client.call_tool is async and CrewAI has partial async support, 
    we must wrap them properly.
    """
    crew_tools = []
    
    mcp_tools = {t.name: t for t in mcp_client.get_tools() if t.name in allowed_tools}
    
    for name, t in mcp_tools.items():
        # A simple synchronous wrapper or async wrapper if CrewAI prefers
        # CrewAI supports langchain BaseTool
        
        # Determine schema from MCP inputSchema
        def create_sync_wrapper(tool_name=name):
            def sync_run(**kwargs):
                # Note: This is a hacky way to run async code in sync context,
                # but CrewAI agents usually run synchronously under the hood.
                # If there's an active loop, use nest_asyncio or similar.
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    import nest_asyncio
                    nest_asyncio.apply()
                    return asyncio.run(mcp_client.call_tool(tool_name, kwargs))
                return asyncio.run(mcp_client.call_tool(tool_name, kwargs))
            return sync_run

        # Basic schema mapping (simplified for this implementation)
        tool = StructuredTool.from_function(
            func=create_sync_wrapper(name),
            name=name,
            description=t.description,
            # We skip explicit args_schema here for simplicity, the LLM will use the argument names directly
        )
        crew_tools.append(tool)
        
    return crew_tools


def create_confluence_crew(mcp_client: MCPClient, provider: str = "openai", model: str = None) -> Crew:
    """
    Create a CrewAI orchestrator for Confluence
    """
    llm = get_llm(provider, model)
    
    search_tools = create_crewai_tools(mcp_client, SEARCH_TOOLS)
    writer_tools = create_crewai_tools(mcp_client, WRITER_TOOLS)
    reviewer_tools = create_crewai_tools(mcp_client, REVIEWER_TOOLS)

    # 1. Define Agents
    search_agent = Agent(
        role='Confluence Search Specialist',
        goal='Find the most relevant Confluence pages',
        backstory='Expert in information retrieval and CQL queries. Always provides page titles and URLs.',
        tools=search_tools,
        llm=llm,
        verbose=True
    )

    writer_agent = Agent(
        role='Confluence Technical Writer',
        goal='Create clear, well-structured documentation',
        backstory='Senior technical writer skilled at XHTML formatting and merging updates securely.',
        tools=writer_tools,
        llm=llm,
        verbose=True
    )

    reviewer_agent = Agent(
        role='Confluence Content Reviewer',
        goal='Ensure documentation meets quality standards before publishing',
        backstory='Meticulous reviewer who catches structural, factual, and formatting issues. Does pre-publish QA.',
        tools=reviewer_tools,
        llm=llm,
        verbose=True
    )

    # Note: the specific execution Tasks must be defined at runtime per user request.
    # This factory just returns the agents for now, or a default crew setup.
    return {
        "search_agent": search_agent,
        "writer_agent": writer_agent,
        "reviewer_agent": reviewer_agent,
        "llm": llm
    }
