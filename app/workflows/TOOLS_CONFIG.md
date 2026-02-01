# HRMS Agent Tools Configuration

This document explains how to switch between **Native LangGraph Tools** and **MCP (Model Context Protocol) Tools** in the HRMS Agent.

## Overview

The agent supports two tool architectures:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Native Tools** | Tools defined in `app/workflows/tools/` as Python functions | Default, simpler setup, includes HITL support |
| **MCP Tools** | Tools exposed via MCP server subprocess | Interoperability, external tool servers, standardized protocol |

## Quick Toggle

### To Use MCP Tools Only (Current Default)

1. **In `app/core/config.py`:**
   ```python
   USE_NATIVE_TOOLS: bool = False
   ```

2. **In `app/workflows/tools/__init__.py`:**
   Comment out the native tool imports (lines 112-121):
   ```python
   # from app.workflows.tools import leave_apply
   # from app.workflows.tools import leave_balance
   # ... etc
   ```

3. **In `app/workflows/prompts.json`:**
   Use MCP tool names in the system prompt (already configured).

### To Use Native Tools

1. **In `app/core/config.py`:**
   ```python
   USE_NATIVE_TOOLS: bool = True
   ```

2. **In `app/workflows/tools/__init__.py`:**
   Uncomment the native tool imports:
   ```python
   from app.workflows.tools import leave_apply
   from app.workflows.tools import leave_balance
   from app.workflows.tools import attendance_apply
   from app.workflows.tools import employee_info
   from app.workflows.tools import leave_apply_admin
   from app.workflows.tools import leave_approve_admin
   from app.workflows.tools import leave_cancel_admin
   from app.workflows.tools import attendance_approve_admin
   from app.workflows.tools import attendance_cancel_admin
   ```

3. **In `app/workflows/prompts.json`:**
   Update the system prompt to use native tool names (see mapping below).

## Tool Name Mapping

| Native Tool Name | MCP Tool Name |
|-----------------|---------------|
| `apply_for_leave` | `hrms_leave_apply_tool` |
| `get_leave_balance` | `hrms_leave_balance_tool` |
| `apply_for_attendance` | `hrms_attendance_apply_tool` |
| `get_employee_info` | `hrms_employee_info_tool` |
| `apply_leave_for_employee` | `hrms_leave_apply_admin_tool` |
| `approve_leave_for_employee` | `hrms_leave_approve_admin_tool` |
| `cancel_leave_for_employee` | `hrms_leave_cancel_admin_tool` |
| `approve_attendance_for_employee` | `hrms_attendance_approve_admin_tool` |
| `cancel_attendance_for_employee` | `hrms_attendance_cancel_admin_tool` |

## Files to Update When Switching

### 1. Config Toggle (`app/core/config.py`)

```python
# MCP Configuration
MCP_SERVER_ENABLED: bool = True
MCP_SERVER_TRANSPORT: str = "stdio"  # "stdio" or "http"
USE_NATIVE_TOOLS: bool = False  # False = MCP only, True = Native tools
```

### 2. Tool Registry (`app/workflows/tools/__init__.py`)

The imports at the bottom of this file control which native tools are registered:

```python
# Import tools to auto-register them
from app.workflows.tools import leave_apply      # Registers apply_for_leave
from app.workflows.tools import leave_balance    # Registers get_leave_balance
from app.workflows.tools import attendance_apply # Registers apply_for_attendance
# ... etc
```

**Comment out all imports to disable native tools.**

### 3. System Prompt (`app/workflows/prompts.json`)

Update the `HRMS TOOLS REFERENCE` section to match the tool names being used.

**For MCP Tools:**
```
| `hrms_leave_apply_tool` | User wants to apply for leave | ...
| `hrms_leave_balance_tool` | User asks about remaining leave | ...
```

**For Native Tools:**
```
| `apply_for_leave` | User wants to apply for leave | ...
| `get_leave_balance` | User asks about remaining leave | ...
```

### 4. HITL Settings (`app/workflows/prompts.json`)

Update `hitl_settings.require_approval_for` and `multi_step_approval_for` arrays:

**For MCP Tools:**
```json
"require_approval_for": [
  "hrms_leave_apply_tool",
  "hrms_leave_approve_admin_tool",
  ...
]
```

**For Native Tools:**
```json
"require_approval_for": [
  "apply_for_leave",
  "approve_leave_for_employee",
  ...
]
```

## Architecture Diagrams

### Native Tools Flow

```
User Request
    ↓
LangGraph Workflow
    ↓
ToolNode (native tools)
    ↓
app/workflows/tools/*.py
    ↓
HRMS API (with HITL interrupts)
```

### MCP Tools Flow

```
User Request
    ↓
LangGraph Workflow
    ↓
ToolNode (MCP tools via langchain-mcp-adapters)
    ↓
MCP Subprocess (mcp_server/server.py)
    ↓
mcp_server/tool_exposer.py
    ↓
HRMS API (no HITL - direct calls)
```

## HITL (Human-in-the-Loop) Support

| Feature | Native Tools | MCP Tools |
|---------|--------------|-----------|
| Tool-level approval | Yes | No* |
| Multi-step approval | Yes | No* |
| Input validation | Yes | No* |
| Document review | Yes | Yes |

*MCP tools bypass HITL because they are executed in a subprocess that cannot access LangGraph's `interrupt()` function. To add HITL to MCP tools, the tool_exposer would need to be refactored to return interrupt signals that are handled by the main workflow.

## MCP Server Options

### STDIO Transport (Default)
MCP server runs as a subprocess, spawned on-demand:
```python
MCP_SERVER_TRANSPORT: str = "stdio"
```

### HTTP Transport
MCP server runs as a separate HTTP service:
```python
MCP_SERVER_TRANSPORT: str = "http"
MCP_SERVER_URL: str = "http://localhost:8001/mcp"
```

To start the HTTP server:
```bash
python mcp_server/server.py http 8001
```

## Troubleshooting

### Tools Not Being Called
1. Check the system prompt references the correct tool names
2. Verify native tool imports are commented/uncommented as needed
3. Check backend logs for `ListToolsRequest` (confirms MCP is loading)

### MCP Subprocess Errors
1. Ensure `MCP_SERVER_ENABLED: bool = True` in config
2. Check Python path includes project root
3. Look for errors in backend terminal output

### "Failed to parse JSONRPC message" Errors
This happens when `print()` statements output to stdout in STDIO mode.
MCP uses stdout exclusively for JSONRPC communication.

**Solution:** The `mcp_server/server.py` now wraps all tool calls with 
`_run_with_stderr_redirect()` which captures stdout and redirects to stderr.

If you add new tools or modify existing ones, ensure they use this wrapper.

### HITL Not Working with MCP
This is expected - MCP tools bypass HITL. Use native tools if HITL is required.

## Environment Variables

You can override config values via environment variables:

```bash
export USE_NATIVE_TOOLS=true   # Enable native tools
export MCP_SERVER_ENABLED=true  # Enable MCP server
export MCP_SERVER_TRANSPORT=stdio  # or "http"
```
