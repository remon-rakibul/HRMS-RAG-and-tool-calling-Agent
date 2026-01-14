"""MCP (Model Context Protocol) integration for HRMS tools.

This package provides:
- MCP server that exposes HRMS tools as MCP tools
- MCP client for consuming external MCP servers
- Adapter to integrate MCP tools into LangGraph workflow
"""

from mcp_server.adapter import get_mcp_tools
from mcp_server.client import get_mcp_client

__all__ = ["get_mcp_tools", "get_mcp_client"]
