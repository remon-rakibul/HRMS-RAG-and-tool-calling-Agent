# MCP (Model Context Protocol) Integration

This directory contains the MCP server implementation that exposes HRMS tools as MCP tools.

## How to Add a New Tool

When you create a new tool in `app/workflows/tools/`, you have **two options**:

### Option 1: Tool Only in LangGraph (No MCP Exposure)

If you only want the tool available in your LangGraph workflow:

1. **Create the tool file** in `app/workflows/tools/your_tool.py`:
```python
from app.workflows.tools import tool_registry
from typing import Annotated

@tool_registry.register
def your_new_tool(
    param1: Annotated[str, "Description of param1"],
    param2: Annotated[int, "Description of param2"] = None
) -> str:
    """Tool description for the LLM."""
    # Your tool logic here
    return "result"
```

2. **Import it in** `app/workflows/tools/__init__.py`:
```python
from app.workflows.tools import your_tool  # noqa: E402, F401
```

**That's it!** The tool will be available in LangGraph automatically.

### Option 2: Tool in Both LangGraph AND MCP (Exposed Externally)

If you want the tool available via MCP (so others can connect to it):

1. **Follow Option 1 steps above** (create tool and register it)

2. **Add wrapper in** `mcp_server/tool_exposer.py`:
```python
from app.workflows.tools.your_tool import your_new_tool

def hrms_your_new_tool(
    param1: str,
    param2: int | None = None
) -> str:
    """Tool description."""
    return your_new_tool(param1=param1, param2=param2)
```

3. **Register in MCP server** `mcp_server/server.py`:
```python
from mcp_server.tool_exposer import hrms_your_new_tool

@mcp.tool()
def hrms_your_new_tool_tool(
    param1: str,
    param2: Optional[int] = None
) -> str:
    """Tool description."""
    return hrms_your_new_tool(param1=param1, param2=param2)
```

**Done!** The tool is now available:
- ✅ In LangGraph workflow (via tool_registry)
- ✅ Via MCP protocol (for external clients)
- ✅ Via FastAPI REST API (`/api/v1/mcp/tools`)

## Running the MCP Server

### STDIO Transport (Default - Internal Use)
The server runs automatically as a subprocess when your FastAPI app needs MCP tools. No manual startup needed.

### HTTP Transport (External Access)
To allow external MCP clients to connect:

```bash
# Start MCP server in HTTP mode
python -m mcp_server.server http 8001

# Or set in .env:
# MCP_SERVER_TRANSPORT=http
# MCP_SERVER_URL=http://localhost:8001/mcp
# MCP_SERVER_PORT=8001
```

Then external clients can connect to `http://your-server:8001/mcp`

## Configuration

Set these in your `.env` file:

```env
# Enable/disable MCP
MCP_SERVER_ENABLED=true

# Transport: "stdio" (subprocess) or "http" (external)
MCP_SERVER_TRANSPORT=stdio

# For HTTP transport
MCP_SERVER_URL=http://localhost:8001/mcp
MCP_SERVER_PORT=8001

# For STDIO transport
MCP_SERVER_COMMAND=python
MCP_SERVER_ARGS=-m,mcp_server.server
```

## Current Tools Exposed via MCP

### Employee Self-Service Tools (4 tools)
1. **`hrms_leave_apply_tool`** - Apply for leave using natural language
   - Supports multiple leave types (Annual, Casual, Sick)
   - Full-day and half-day options
   - Automatic date parsing and validation

2. **`hrms_leave_balance_tool`** - Get leave balance
   - Instant balance retrieval
   - Multi-leave type support
   - Context-aware (uses logged-in employee ID)

3. **`hrms_attendance_apply_tool`** - Apply for manual attendance
   - Flexible time entry (in-time, out-time, or both)
   - Reason validation
   - Automatic date formatting

4. **`hrms_employee_info_tool`** - Get employee personal information
   - Retrieve employee details (name, department, designation, etc.)
   - Context-aware (uses logged-in employee ID)
   - Answers questions like "Who am I?", "Where do I work?"

### Admin Tools (5 tools)
4. **`hrms_leave_apply_admin_tool`** - Admin: Apply leave for employees
   - Employee search by name
   - Hierarchy validation
   - Automated 18-step leave application workflow

5. **`hrms_leave_approve_admin_tool`** - Admin: Approve leave requests
   - Search employee by name
   - Find leave request by applied date
   - Automated approval workflow (9 steps) with email notifications

6. **`hrms_leave_cancel_admin_tool`** - Admin: Cancel leave requests
   - Search employee by name
   - Find leave request by applied date
   - Automated cancellation workflow (5 steps) with email notifications

7. **`hrms_attendance_approve_admin_tool`** - Admin: Approve attendance requests
   - Search employee by name
   - Find attendance request by date and time type
   - Automated approval workflow (6 steps) with email notifications

8. **`hrms_attendance_cancel_admin_tool`** - Admin: Cancel attendance requests
   - Search employee by name
   - Find attendance request by date and time type
   - Automated cancellation workflow (6 steps) with email notifications

**Total: 9 HRMS tools exposed via MCP protocol**