"""MCP (Model Context Protocol) API endpoints.

Provides HTTP interface to MCP functionality including:
- Listing available tools from all MCP servers
- Executing tool calls via MCP
- Managing MCP server configuration
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from mcp_server.client import get_mcp_client
from mcp_server.adapter import get_mcp_tools
from langchain_core.tools import BaseTool

router = APIRouter()


class ToolCallRequest(BaseModel):
    """Request model for tool execution."""
    tool_name: str
    arguments: Dict[str, Any]
    server_name: Optional[str] = None  # If None, searches all servers


class ToolCallResponse(BaseModel):
    """Response model for tool execution."""
    result: str
    server_name: str
    tool_name: str


@router.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """List all available tools from all configured MCP servers.
    
    Returns:
        Dictionary with server names as keys and lists of tool information as values
    """
    try:
        tools = await get_mcp_tools()
        
        # Group tools by server
        # Get configured server names to help with grouping
        from mcp_server.client import get_mcp_client_config
        server_configs = get_mcp_client_config()
        configured_servers = list(server_configs.keys())
        
        tools_by_server: Dict[str, List[Dict[str, Any]]] = {}
        
        for tool in tools:
            # Extract server name from tool name
            tool_name = tool.name
            server_name = "unknown"
            actual_tool_name = tool_name
            
            # Check if tool name has server prefix (format: "server_name:tool_name")
            if ":" in tool_name:
                server_name, actual_tool_name = tool_name.split(":", 1)
            # Check if tool name starts with known server prefix (e.g., "hrms_")
            elif tool_name.startswith("hrms_"):
                server_name = "hrms"
                actual_tool_name = tool_name
            # Try to match against configured server names
            else:
                for server in configured_servers:
                    if tool_name.startswith(f"{server}_"):
                        server_name = server
                        actual_tool_name = tool_name
                        break
            
            if server_name not in tools_by_server:
                tools_by_server[server_name] = []
            
            # Handle args_schema - it might be a dict or a Pydantic model
            args_schema = {}
            if hasattr(tool, 'args_schema') and tool.args_schema:
                if isinstance(tool.args_schema, dict):
                    args_schema = tool.args_schema
                elif hasattr(tool.args_schema, 'model_json_schema'):
                    # Pydantic v2
                    args_schema = tool.args_schema.model_json_schema()
                elif hasattr(tool.args_schema, 'schema'):
                    # Pydantic v1
                    args_schema = tool.args_schema.schema()
                else:
                    # Try to convert to dict
                    try:
                        args_schema = dict(tool.args_schema) if tool.args_schema else {}
                    except (TypeError, ValueError):
                        args_schema = {}
            
            tools_by_server[server_name].append({
                "name": actual_tool_name,
                "full_name": tool_name,
                "description": tool.description,
                "args_schema": args_schema
            })
        
        return {
            "servers": tools_by_server,
            "total_tools": len(tools)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing MCP tools: {str(e)}")


@router.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest) -> ToolCallResponse:
    """Execute a tool call via MCP.
    
    Args:
        request: Tool call request with tool name, arguments, and optional server name
        
    Returns:
        Tool execution result
    """
    try:
        # Get all MCP tools (they're already LangChain tools)
        tools = await get_mcp_tools()
        
        # Find tool by name
        target_tool = None
        for tool in tools:
            # Check if tool name matches (with or without server prefix)
            if tool.name == request.tool_name:
                target_tool = tool
                break
            elif ":" in tool.name:
                server_name, actual_tool_name = tool.name.split(":", 1)
                if actual_tool_name == request.tool_name:
                    target_tool = tool
                    break
                elif request.server_name and server_name == request.server_name and actual_tool_name == request.tool_name:
                    target_tool = tool
                    break
        
        if not target_tool:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{request.tool_name}' not found on any MCP server"
            )
        
        # Extract server name from tool name
        tool_name = target_tool.name
        if ":" in tool_name:
            server_name = tool_name.split(":", 1)[0]
        elif tool_name.startswith("hrms_"):
            server_name = "hrms"
        else:
            # Try to match against configured server names
            from mcp_server.client import get_mcp_client_config
            server_configs = get_mcp_client_config()
            server_name = request.server_name or "unknown"
            for server in server_configs.keys():
                if tool_name.startswith(f"{server}_"):
                    server_name = server
                    break
        
        # Execute the tool (it's a LangChain tool, so we can invoke it directly)
        try:
            result = await target_tool.ainvoke(request.arguments)
            result_str = str(result) if result else ""
        except Exception as e:
            # Fallback to sync invoke if async fails
            result = target_tool.invoke(request.arguments)
            result_str = str(result) if result else ""
        
        return ToolCallResponse(
            result=result_str,
            server_name=server_name,
            tool_name=request.tool_name
        )
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling MCP tool: {str(e)}")


@router.get("/servers")
async def list_servers() -> Dict[str, Any]:
    """List all configured MCP servers.
    
    Returns:
        Dictionary with server configuration information
    """
    try:
        from mcp_server.client import get_mcp_client_config
        config = get_mcp_client_config()
        
        servers = []
        for server_name, server_config in config.items():
            servers.append({
                "name": server_name,
                "transport": server_config.get("transport", "unknown"),
                "config": {k: v for k, v in server_config.items() if k != "transport"}
            })
        
        return {
            "servers": servers,
            "total": len(servers)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing MCP servers: {str(e)}")
