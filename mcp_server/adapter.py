"""Adapter to integrate MCP tools into LangGraph workflow.

This module provides helper functions to get MCP tools (which are automatically
converted to LangChain BaseTool instances by langchain-mcp-adapters).
"""

from typing import List, Optional
from langchain_core.tools import BaseTool
from mcp_server.client import get_mcp_client
from app.core.config import settings


async def get_mcp_tools() -> List[BaseTool]:
    """Get all MCP tools as LangChain BaseTool instances.
    
    This function:
    1. Initializes MultiServerMCPClient with local and external MCP servers
    2. Fetches tools from all configured MCP servers
    3. Returns LangChain BaseTool instances ready for LangGraph
    
    Returns:
        List of LangChain BaseTool instances from all MCP servers
    """
    # Check if MCP is enabled
    if not getattr(settings, 'MCP_SERVER_ENABLED', True):
        return []
    
    try:
        client = await get_mcp_client()
        tools = await client.get_tools()
        return tools
    except Exception as e:
        print(f"[MCP] Error getting MCP tools: {str(e)}", flush=True)
        return []
