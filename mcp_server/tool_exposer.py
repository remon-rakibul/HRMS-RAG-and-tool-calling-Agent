"""Tool exposer for HRMS tools as MCP tools.

This module wraps existing HRMS LangChain tools and exposes them as MCP tools
using fastmcp decorators.
"""

from typing import Annotated, Optional
from app.workflows.tools.leave_apply import apply_for_leave
from app.workflows.tools.leave_balance import get_leave_balance
from app.workflows.tools.attendance_apply import apply_for_manual_attendance
from app.workflows.tools.employee_info import get_employee_info
from app.workflows.tools.leave_apply_admin import apply_leave_for_employee
from app.workflows.tools.leave_approve_admin import approve_leave_for_employee
from app.workflows.tools.leave_cancel_admin import cancel_leave_for_employee
from app.workflows.tools.attendance_approve_admin import approve_attendance_for_employee
from app.workflows.tools.attendance_cancel_admin import cancel_attendance_for_employee


# These functions will be decorated with @mcp.tool() in server.py
# We define them here as wrappers to maintain clean separation

def hrms_leave_apply(
    start_date: Annotated[str, "Leave start date in YYYY-MM-DD format (e.g., '2024-12-01')"],
    total_days: Annotated[int, "Total number of leave days (e.g., 1, 2, 3)"],
    reason: Annotated[str, "Reason or purpose for the leave application"],
    employee_id: Annotated[Optional[int], "Employee ID (optional, defaults to logged-in user)"] = None,
    leave_type_id: Annotated[Optional[int], "Leave type ID: 6=Annual, 15=Casual, 2=Sick (optional, defaults to 6)"] = None,
    day_leave_type: Annotated[Optional[str], "Leave duration: 'Full-Day' or 'Half-Day' (optional, defaults to Full-Day)"] = None,
    half_day_type: Annotated[Optional[str], "If Half-Day, specify: 'First-Half' or 'Second-Half' (optional)"] = None
) -> str:
    """Apply for leave in the HRMS system."""
    return apply_for_leave(
        start_date=start_date,
        total_days=total_days,
        reason=reason,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        day_leave_type=day_leave_type,
        half_day_type=half_day_type
    )


def hrms_leave_balance(
    employee_id: Annotated[Optional[int], "Employee ID (optional, defaults to logged-in user)"] = None
) -> str:
    """Get the current user's leave balance from the HRMS system."""
    return get_leave_balance(employee_id=employee_id)


def hrms_attendance_apply(
    attendance_date: Annotated[str, "Attendance date in YYYY-MM-DD format (e.g., '2026-01-04')"],
    reason: Annotated[str, "Reason for manual attendance."],
    in_time: Annotated[Optional[str], "In-time in HH:MM format (e.g., '09:00'). Provide if user wants to mark in-time"] = None,
    out_time: Annotated[Optional[str], "Out-time in HH:MM format (e.g., '18:00'). Provide if user wants to mark out-time"] = None,
    time_request_for: Annotated[Optional[str], "Time request type: 'Both', 'In-Time', or 'Out-Time'. Auto-detected from in_time/out_time if not provided"] = None,
    employee_id: Annotated[Optional[int], "Employee ID (optional, defaults to logged-in user)"] = None
) -> str:
    """Apply for manual attendance in the HRMS system."""
    return apply_for_manual_attendance(
        attendance_date=attendance_date,
        reason=reason,
        in_time=in_time,
        out_time=out_time,
        time_request_for=time_request_for,
        employee_id=employee_id
    )


def hrms_employee_info(
    employee_id: Annotated[Optional[int], "Employee ID (optional, defaults to logged-in user)"] = None
) -> str:
    """Get the current user's employee personal information from the HRMS system."""
    return get_employee_info(employee_id=employee_id)


def hrms_leave_apply_admin(
    employee_name: Annotated[str, "Employee name to search for (e.g., 'Neha Muquid')"],
    start_date: Annotated[str, "Leave start date in YYYY-MM-DD format (e.g., '2024-01-14')"],
    total_days: Annotated[int, "Total number of leave days (e.g., 1, 2, 3)"],
    reason: Annotated[str, "Reason or purpose for the leave application"],
    leave_type_id: Annotated[Optional[int], "Leave type ID: 6=Annual, 15=Casual, 2=Sick (optional, defaults to 2)"] = None,
    day_leave_type: Annotated[Optional[str], "Leave duration: 'Full-Day' or 'Half-Day' (optional, defaults to Full-Day)"] = None,
    half_day_type: Annotated[Optional[str], "If Half-Day, specify: 'First-Half' or 'Second-Half' (optional)"] = None
) -> str:
    """Apply leave for any employee under admin hierarchy. Search by name, validate hierarchy, and submit leave request."""
    return apply_leave_for_employee(
        employee_name=employee_name,
        start_date=start_date,
        total_days=total_days,
        reason=reason,
        leave_type_id=leave_type_id,
        day_leave_type=day_leave_type,
        half_day_type=half_day_type
    )


def hrms_leave_approve_admin(
    employee_name: Annotated[str, "Employee name to search for (e.g., 'Neha Muquid')"],
    applied_date: Annotated[str, "Date the leave was applied for in YYYY-MM-DD format (e.g., '2026-01-12')"],
    remarks: Annotated[Optional[str], "Approval remarks (optional, defaults to 'Approved')"] = None
) -> str:
    """Approve leave request for an employee. Search by name, find leave request by applied date, and approve it."""
    return approve_leave_for_employee(
        employee_name=employee_name,
        applied_date=applied_date,
        remarks=remarks
    )


def hrms_leave_cancel_admin(
    employee_name: Annotated[str, "Employee name to search for (e.g., 'Neha Muquid')"],
    applied_date: Annotated[str, "Date the leave was applied for in YYYY-MM-DD format (e.g., '2026-01-12')"],
    remarks: Annotated[Optional[str], "Cancellation remarks (optional, defaults to 'Cancelled')"] = None
) -> str:
    """Cancel leave request for an employee. Search by name, find leave request by applied date, and cancel it."""
    return cancel_leave_for_employee(
        employee_name=employee_name,
        applied_date=applied_date,
        remarks=remarks
    )


def hrms_attendance_approve_admin(
    employee_name: Annotated[str, "Employee name to search for (e.g., 'Neha Muquid')"],
    applied_date: Annotated[str, "Date the attendance was applied for in YYYY-MM-DD format (e.g., '2026-01-12')"],
    requested_time: Annotated[str, "Time request type: 'In-Time', 'Out-Time', or 'Both' (can also accept 'intime', 'outtime', 'both')"],
    remarks: Annotated[Optional[str], "Approval remarks (optional, defaults to 'Approved')"] = None
) -> str:
    """Approve manual attendance request for an employee. Search by name, find attendance request by applied date and time type, and approve it."""
    return approve_attendance_for_employee(
        employee_name=employee_name,
        applied_date=applied_date,
        requested_time=requested_time,
        remarks=remarks
    )


def hrms_attendance_cancel_admin(
    employee_name: Annotated[str, "Employee name to search for (e.g., 'Neha Muquid')"],
    applied_date: Annotated[str, "Date the attendance was applied for in YYYY-MM-DD format (e.g., '2026-01-12')"],
    requested_time: Annotated[str, "Time request type: 'In-Time', 'Out-Time', or 'Both' (can also accept 'intime', 'outtime', 'both')"],
    remarks: Annotated[Optional[str], "Cancellation reason (optional, defaults to 'Cancelled')"] = None
) -> str:
    """Cancel manual attendance request for an employee. Search by name, find attendance request by applied date and time type, and cancel it."""
    return cancel_attendance_for_employee(
        employee_name=employee_name,
        applied_date=applied_date,
        requested_time=requested_time,
        remarks=remarks
    )
