import os
import sys
import asyncio
from typing import List, Any, Dict
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import StructuredTool

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = None
        self._tools_cache = []
        self.transport_ctx = None

    async def connect(self):
        """
        Connects to the local Confluence MCP server subprocess.
        """
        # We run the server by executing the package module
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "src.confluence_mcp"],
            env=os.environ.copy()
        )
        
        self.transport_ctx = stdio_client(server_params)
        # Properly enter the context manager
        self.read_stream, self.write_stream = await self.transport_ctx.__aenter__()
        
        self.session = ClientSession(self.read_stream, self.write_stream)
        await self.session.__aenter__()
        await self.session.initialize()
        
        # Cache tools on connect
        result = await self.session.list_tools()
        self._tools_cache = result.tools

    async def close(self):
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception:
                pass
        if self.transport_ctx:
            try:
                await self.transport_ctx.__aexit__(None, None, None)
            except (Exception, RuntimeError, GeneratorExit):
                pass

    def get_tools(self):
        """
        Returns the list of tools available on the server.
        """
        return self._tools_cache

    async def call_tool(self, name: str, arguments: dict) -> str:
        if not self.session:
             raise RuntimeError("MCP Client not connected")
        
        try:
            result = await self.session.call_tool(name, arguments=arguments)
        except Exception as e:
            return f"Error executing tool {name}: {str(e)}"
        
        text_output = []
        for content in result.content:
            if content.type == "text":
                text_output.append(content.text)
            elif content.type == "image":
                 text_output.append(f"[Image: {content.mimeType}]")
        
        final_text = "\n".join(text_output)
        if result.isError:
             return f"Error: {final_text}"
        return final_text
