"""MCP server implementation using fastmcp.

This server exposes HRMS tools as MCP tools using STDIO or HTTP transport.
Run this as a standalone process:
  - STDIO: python -m mcp_server.server (or python -m mcp_server.server stdio)
  - HTTP: python -m mcp_server.server http [port] (default port: 8001)

IMPORTANT: In STDIO mode, stdout is reserved for JSONRPC messages.
All print() statements from tools are redirected to stderr to prevent
corrupting the MCP protocol.
"""

from typing import Optional
import sys
import os
from pathlib import Path
from contextlib import redirect_stdout
import io

# Check if running in STDIO mode (default)
_transport_arg = sys.argv[1] if len(sys.argv) > 1 else "stdio"
_is_stdio_mode = _transport_arg != "http"

# Save original stdout for MCP JSONRPC communication
_original_stdout = sys.stdout

if _is_stdio_mode:
    # Suppress some noisy logs
    os.environ.setdefault("HTTPX_LOG_LEVEL", "WARNING")

# Add project root to Python path so imports work when running as subprocess
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastmcp import FastMCP
from mcp_server.tool_exposer import (
    hrms_leave_apply,
    hrms_leave_balance,
    hrms_attendance_apply,
    hrms_employee_info,
    hrms_leave_apply_admin,
    hrms_leave_approve_admin,
    hrms_leave_cancel_admin,
    hrms_attendance_approve_admin,
    hrms_attendance_cancel_admin
)

# Create FastMCP instance
mcp = FastMCP("HRMS")


def _run_with_stderr_redirect(func, *args, **kwargs):
    """Run a function with stdout redirected to stderr.
    
    This prevents print() statements from corrupting MCP JSONRPC in STDIO mode.
    """
    if _is_stdio_mode:
        # Capture stdout and redirect to stderr
        captured = io.StringIO()
        with redirect_stdout(captured):
            result = func(*args, **kwargs)
        # Print captured output to stderr
        output = captured.getvalue()
        if output:
            print(output, file=sys.stderr, end='')
        return result
    else:
        return func(*args, **kwargs)


# Register HRMS tools as MCP tools
@mcp.tool()
def hrms_leave_apply_tool(
    start_date: str,
    total_days: int,
    reason: str,
    employee_id: Optional[int] = None,
    leave_type_id: Optional[int] = None,
    day_leave_type: Optional[str] = None,
    half_day_type: Optional[str] = None
) -> str:
    """Apply for leave in the HRMS system."""
    return _run_with_stderr_redirect(
        hrms_leave_apply,
        start_date=start_date,
        total_days=total_days,
        reason=reason,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        day_leave_type=day_leave_type,
        half_day_type=half_day_type
    )


@mcp.tool()
def hrms_leave_balance_tool(
    employee_id: Optional[int] = None
) -> str:
    """Get the current user's leave balance from the HRMS system."""
    return _run_with_stderr_redirect(hrms_leave_balance, employee_id=employee_id)


@mcp.tool()
def hrms_attendance_apply_tool(
    attendance_date: str,
    reason: str,
    in_time: Optional[str] = None,
    out_time: Optional[str] = None,
    time_request_for: Optional[str] = None,
    employee_id: Optional[int] = None
) -> str:
    """Apply for manual attendance in the HRMS system."""
    return _run_with_stderr_redirect(
        hrms_attendance_apply,
        attendance_date=attendance_date,
        reason=reason,
        in_time=in_time,
        out_time=out_time,
        time_request_for=time_request_for,
        employee_id=employee_id
    )


@mcp.tool()
def hrms_employee_info_tool(
    employee_id: Optional[int] = None
) -> str:
    """Get the current user's employee personal information from the HRMS system."""
    return _run_with_stderr_redirect(hrms_employee_info, employee_id=employee_id)


@mcp.tool()
def hrms_leave_apply_admin_tool(
    employee_name: str,
    start_date: str,
    total_days: int,
    reason: str,
    leave_type_id: Optional[int] = None,
    day_leave_type: Optional[str] = None,
    half_day_type: Optional[str] = None
) -> str:
    """Apply leave for any employee under admin hierarchy. Search by name, validate hierarchy, and submit leave request."""
    return _run_with_stderr_redirect(
        hrms_leave_apply_admin,
        employee_name=employee_name,
        start_date=start_date,
        total_days=total_days,
        reason=reason,
        leave_type_id=leave_type_id,
        day_leave_type=day_leave_type,
        half_day_type=half_day_type
    )


@mcp.tool()
def hrms_leave_approve_admin_tool(
    employee_name: str,
    applied_date: str,
    remarks: Optional[str] = None
) -> str:
    """Approve leave request for an employee. Search by name, find leave request by applied date, and approve it."""
    return _run_with_stderr_redirect(
        hrms_leave_approve_admin,
        employee_name=employee_name,
        applied_date=applied_date,
        remarks=remarks
    )


@mcp.tool()
def hrms_leave_cancel_admin_tool(
    employee_name: str,
    applied_date: str,
    remarks: Optional[str] = None
) -> str:
    """Cancel leave request for an employee. Search by name, find leave request by applied date, and cancel it."""
    return _run_with_stderr_redirect(
        hrms_leave_cancel_admin,
        employee_name=employee_name,
        applied_date=applied_date,
        remarks=remarks
    )


@mcp.tool()
def hrms_attendance_approve_admin_tool(
    employee_name: str,
    applied_date: str,
    requested_time: str,
    remarks: Optional[str] = None
) -> str:
    """Approve manual attendance request for an employee. Search by name, find attendance request by applied date and time type, and approve it."""
    return _run_with_stderr_redirect(
        hrms_attendance_approve_admin,
        employee_name=employee_name,
        applied_date=applied_date,
        requested_time=requested_time,
        remarks=remarks
    )


@mcp.tool()
def hrms_attendance_cancel_admin_tool(
    employee_name: str,
    applied_date: str,
    requested_time: str,
    remarks: Optional[str] = None
) -> str:
    """Cancel manual attendance request for an employee. Search by name, find attendance request by applied date and time type, and cancel it."""
    return _run_with_stderr_redirect(
        hrms_attendance_cancel_admin,
        employee_name=employee_name,
        applied_date=applied_date,
        requested_time=requested_time,
        remarks=remarks
    )


if __name__ == "__main__":
    # Parse command line arguments
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
    
    if transport == "http":
        # Run MCP server with HTTP transport for external access
        print(f"[MCP Server] Starting HTTP server on port {port}...", flush=True)
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        # Run MCP server with STDIO transport (default, for subprocess use)
        # Note: Tool executions redirect their stdout to stderr via _run_with_stderr_redirect
        # This keeps the MCP JSONRPC protocol clean on stdout
        mcp.run(transport="stdio")
