"""MCP client for consuming external MCP servers.

This module provides functionality to connect to and consume tools from
external MCP servers using MultiServerMCPClient from langchain-mcp-adapters.
"""

from typing import Dict, Any, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from app.core.config import settings
import os


def get_mcp_client_config() -> Dict[str, Dict[str, Any]]:
    """Get MCP client configuration from settings.
    
    Returns:
        Dictionary mapping server names to their configuration
    """
    config: Dict[str, Dict[str, Any]] = {}
    
    # Add local HRMS MCP server
    if getattr(settings, 'MCP_SERVER_ENABLED', True):
        mcp_transport = getattr(settings, 'MCP_SERVER_TRANSPORT', 'stdio')
        mcp_url = getattr(settings, 'MCP_SERVER_URL', 'http://localhost:8001/mcp')
        
        if mcp_transport == "http":
            # HTTP transport for external access
            config["hrms"] = {
                "transport": "http",
                "url": mcp_url
            }
        else:
            # STDIO transport (default, for subprocess use)
            server_command = getattr(settings, 'MCP_SERVER_COMMAND', 'python')
            server_args = getattr(settings, 'MCP_SERVER_ARGS', ['-m', 'mcp_server.server'])
            
            # Get absolute path to server.py
            from pathlib import Path
            project_root = Path(__file__).parent.parent
            server_path = project_root / "mcp_server" / "server.py"
            
            config["hrms"] = {
                "transport": "stdio",
                "command": server_command,
                "args": [str(server_path)] if server_path.exists() else server_args
            }
    
    # Add external MCP servers from configuration
    external_servers = getattr(settings, 'MCP_EXTERNAL_SERVERS', [])
    if isinstance(external_servers, list):
        for idx, server_config in enumerate(external_servers):
            if isinstance(server_config, dict):
                server_name = server_config.get("name", f"external_{idx}")
                config[server_name] = {
                    "transport": server_config.get("transport", "stdio"),
                    **{k: v for k, v in server_config.items() if k != "name"}
                }
    
    return config


async def get_mcp_client() -> MultiServerMCPClient:
    """Create and return a MultiServerMCPClient instance.
    
    Returns:
        MultiServerMCPClient configured with local and external MCP servers
    """
    config = get_mcp_client_config()
    return MultiServerMCPClient(config)
