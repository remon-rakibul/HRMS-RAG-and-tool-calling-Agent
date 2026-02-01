"""HRMS Admin Leave Application Tool.

This tool allows admins to apply leave for any employee by searching for them by name.
It handles the complete leave application workflow including employee search, hierarchy validation,
and submission through 18 HRMS API endpoints.
"""

from typing import Annotated, Optional, Dict, Any, List
from datetime import datetime, timedelta
import httpx
import urllib3
import json
from app.workflows.tools import tool_registry
from app.workflows.prompt_loader import should_require_approval
from langgraph.types import interrupt

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# HRMS API Configuration - Admin credentials for API authentication
HRMS_BASE_URL = "https://abcl.myrecombd.com:9999"
HRMS_USERNAME = "demo_admin"
HRMS_PASSWORD = "Demo@2024"

# Default values
DEFAULT_LEAVE_TYPE_ID = 2  # Sick Leave


def _encrypt_value(value: str) -> Optional[str]:
    """Encrypt a value using the HRMS encrypt endpoint."""
    try:
        response = httpx.post(
            f"{HRMS_BASE_URL}/encrypt",
            json=value,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
            verify=False
        )
        
        if response.status_code == 200:
            return response.text.strip().strip('"')
        else:
            print(f"[HRMS Admin] Encrypt failed: HTTP {response.status_code}", flush=True)
            return None
    except Exception as e:
        print(f"[HRMS Admin] Encrypt error: {str(e)}", flush=True)
        return None


def _get_hrms_token() -> Optional[str]:
    """Authenticate with HRMS and get bearer token."""
    print("[HRMS Admin] Authenticating...", flush=True)
    
    # Encrypt credentials
    encrypted_username = _encrypt_value(HRMS_USERNAME)
    encrypted_password = _encrypt_value(HRMS_PASSWORD)
    
    if not encrypted_username or not encrypted_password:
        print("[HRMS Admin] Failed to encrypt credentials", flush=True)
        return None
    
    # Login
    try:
        login_response = httpx.post(
            f"{HRMS_BASE_URL}/api/ControlPanel/Access/login",
            json={
                "username": encrypted_username,
                "password": encrypted_password
            },
            headers={"Content-Type": "application/json"},
            timeout=30.0,
            verify=False
        )
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("token") or data.get("access_token") or data.get("accessToken")
            if token:
                print("[HRMS Admin] Authentication successful", flush=True)
                return token
            
        print(f"[HRMS Admin] Login failed: {login_response.status_code}", flush=True)
        return None
            
    except Exception as e:
        print(f"[HRMS Admin] Login error: {str(e)}", flush=True)
        return None


def _format_datetime(date_str: str) -> str:
    """Convert date string to ISO datetime format."""
    current_year = datetime.now().year
    
    formats_with_year = [
        "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y",
        "%B %d, %Y", "%b %d, %Y", "%Y-%m-%dT%H:%M:%S"
    ]
    
    for fmt in formats_with_year:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.year < current_year:
                dt = dt.replace(year=current_year)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    formats_without_year = ["%B %d", "%b %d", "%m-%d", "%m/%d"]
    
    for fmt in formats_without_year:
        try:
            dt = datetime.strptime(date_str, fmt)
            dt = dt.replace(year=current_year)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return date_str


def _generate_leave_days_json(from_date: str, total_days: int) -> List[Dict]:
    """Generate LeaveDaysJson array for the leave request."""
    start_dt = datetime.strptime(from_date, "%Y-%m-%d")
    leave_days = []
    
    for i in range(int(total_days)):
        current_date = start_dt + timedelta(days=i)
        leave_days.append({
            "SL": i + 1,
            "Date": current_date.strftime("%Y-%m-%d"),
            "DayName": current_date.strftime("%A"),
            "WorkShiftId": 1,
            "WorkShiftName": "General",
            "Status": "Leave"
        })
    
    return leave_days


def _search_employee_by_name(token: str, employee_name: str) -> Optional[Dict]:
    """Search for employee by name and return employeeId and employeeName.
    
    Returns:
        Dict with 'employeeId' and 'employeeName' if found,
        Dict with 'error' key if multiple matches,
        None if not found or error occurred
    """
    print(f"[HRMS Admin] Searching for employee: {employee_name}", flush=True)
    
    try:
        response = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Employee/Info/GetEmployeeServiceData",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
            verify=False
        )
        
        if response.status_code != 200:
            print(f"[HRMS Admin] GetEmployeeServiceData failed: HTTP {response.status_code}", flush=True)
            return None
        
        data = response.json()
        name_lower = employee_name.lower().strip()
        matches = []
        
        # Handle different response structures
        employees = []
        if isinstance(data, list):
            employees = data
        elif isinstance(data, dict):
            # Try common keys for employee arrays
            employees = (data.get("data") or data.get("employees") or 
                        data.get("result") or data.get("items") or [])
            # If still empty, check if the dict itself contains employee fields
            if not employees and ("employeeId" in data or "id" in data):
                employees = [data]
        
        print(f"[HRMS Admin] Found {len(employees)} total employees in response", flush=True)
        
        # Search through employees
        for emp in employees:
            if not isinstance(emp, dict):
                continue
                
            # Try multiple possible name fields
            emp_name = (emp.get("employeeName") or emp.get("name") or 
                       emp.get("fullName") or emp.get("employee_name") or
                       emp.get("EmployeeName") or emp.get("Name") or "")
            
            if not emp_name:
                continue
                
            emp_name_lower = emp_name.lower()
            # Case-insensitive partial matching
            if name_lower in emp_name_lower or emp_name_lower in name_lower:
                matches.append({
                    "employeeId": emp.get("employeeId") or emp.get("id") or emp.get("EmployeeId"),
                    "employeeName": emp_name
                })
        
        if len(matches) == 0:
            print(f"[HRMS Admin] No employee found matching '{employee_name}'", flush=True)
            return None
        
        if len(matches) > 1:
            match_names = [m["employeeName"] for m in matches]
            print(f"[HRMS Admin] Multiple matches found: {match_names}", flush=True)
            return {
                "error": f"Multiple employees found matching '{employee_name}'. Please provide a more specific name. Matches: {', '.join(match_names[:5])}"
            }
        
        result = matches[0]
        if not result.get("employeeId"):
            print(f"[HRMS Admin] Employee found but no employeeId in response", flush=True)
            return None
        
        print(f"[HRMS Admin] ✓ Found employee: {result['employeeName']} (ID: {result['employeeId']})", flush=True)
        return result
        
    except Exception as e:
        print(f"[HRMS Admin] Search error: {str(e)}", flush=True)
        return None


@tool_registry.register
def apply_leave_for_employee(
    employee_name: Annotated[str, "Employee name to search for (e.g., 'Neha Muquid')"],
    start_date: Annotated[str, "Leave start date in YYYY-MM-DD format (e.g., '2024-01-14')"],
    total_days: Annotated[int, "Total number of leave days (e.g., 1, 2, 3)"],
    reason: Annotated[str, "Reason or purpose for the leave application"],
    leave_type_id: Annotated[Optional[int], "Leave type ID: 6=Annual, 15=Casual, 2=Sick (optional, defaults to 2)"] = None,
    day_leave_type: Annotated[Optional[str], "Leave duration: 'Full-Day' or 'Half-Day' (optional, defaults to Full-Day)"] = None,
    half_day_type: Annotated[Optional[str], "If Half-Day, specify: 'First-Half' or 'Second-Half' (optional)"] = None
) -> str:
    """Apply leave for any employee under admin hierarchy. Search by name, validate hierarchy, and submit leave request.
    
    This tool allows admins to apply leave for employees by searching for them by name.
    It handles the complete workflow including employee search, hierarchy validation,
    and submission through all required HRMS API endpoints.
    
    Examples:
    - "apply leave for neha muquid on 14th january for 1 day as sick leave"
    - "apply 3 days leave for john doe starting tomorrow"
    - "apply half day leave for jane smith on friday afternoon"
    """
    # Set defaults for optional parameters
    if leave_type_id is None:
        leave_type_id = DEFAULT_LEAVE_TYPE_ID
    
    if day_leave_type is None:
        day_leave_type = "Full-Day"
    
    # Normalize day_leave_type
    if day_leave_type.lower() in ["half", "half-day", "half day"]:
        day_leave_type = "Half-Day"
        if half_day_type is None:
            half_day_type = "First-Half"  # Default to morning
    else:
        day_leave_type = "Full-Day"
        half_day_type = None
    
    print("\n" + "="*70, flush=True)
    print("[HRMS Admin] ADMIN LEAVE APPLICATION PROCESS STARTED", flush=True)
    print("="*70, flush=True)
    print(f"[HRMS Admin] Employee Name: {employee_name}", flush=True)
    print(f"[HRMS Admin] Leave Type ID: {leave_type_id}", flush=True)
    print(f"[HRMS Admin] Day Type: {day_leave_type}" + (f" ({half_day_type})" if half_day_type else ""), flush=True)
    print(f"[HRMS Admin] Total Days: {total_days}", flush=True)
    print(f"[HRMS Admin] Reason: {reason}", flush=True)
    print("-" * 70, flush=True)
    
    # Step 1: Authenticate
    token = _get_hrms_token()
    if not token:
        return "❌ Failed to authenticate with HRMS system."
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Search for employee
    emp_result = _search_employee_by_name(token, employee_name)
    if not emp_result:
        return f"❌ No employee found matching '{employee_name}'. Please check the name and try again."
    
    if "error" in emp_result:
        return f"❌ {emp_result['error']}"
    
    employee_id = emp_result["employeeId"]
    found_name = emp_result["employeeName"]
    
    print(f"[HRMS Admin] Using Employee ID: {employee_id}", flush=True)
    print("-" * 70, flush=True)
    
    # Format dates
    from_date = _format_datetime(start_date)
    try:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    except ValueError:
        return f"❌ Invalid date format: {start_date}. Please use YYYY-MM-DD format."
    
    to_dt = from_dt + timedelta(days=total_days - 1)
    to_date = to_dt.strftime("%Y-%m-%d")
    
    print(f"[HRMS Admin] Leave Period: {from_date} to {to_date} ({total_days} days)", flush=True)
    print("-" * 70, flush=True)
    
    # Map leave_type_id to human-readable name
    leave_type_names = {
        2: "Sick Leave",
        6: "Annual Leave",
        15: "Casual Leave"
    }
    leave_type_name = leave_type_names.get(leave_type_id, f"Leave Type {leave_type_id}")
    
    # HITL: Request confirmation before applying leave for employee
    if should_require_approval("apply_leave_for_employee"):
        print("[HRMS Admin] HITL: Requesting leave application confirmation...", flush=True)
        
        confirmation = interrupt({
            "action": "admin_leave_application",
            "message": "Please confirm this leave application on behalf of the employee:",
            "details": {
                "employee": found_name,
                "employee_id": employee_id,
                "leave_type": leave_type_name,
                "period": f"{from_date} to {to_date}",
                "days": total_days,
                "day_type": day_leave_type + (f" ({half_day_type})" if half_day_type else ""),
                "reason": reason
            },
            "editable_fields": ["reason"],
            "current_values": {
                "reason": reason
            },
            "options": ["approve", "reject"]
        })
        
        if confirmation.get("action") == "reject":
            print("[HRMS Admin] HITL: Admin leave application rejected", flush=True)
            return "❌ Leave application cancelled."
        
        # Apply any edits from user
        if confirmation.get("reason"):
            reason = confirmation["reason"]
            print(f"[HRMS Admin] HITL: Reason updated to: {reason}", flush=True)
        
        print("[HRMS Admin] HITL: Admin leave application confirmed", flush=True)
    
    try:
        # Endpoint 1: GetEmployeeServiceData (already called for search, but call again as per workflow)
        print("[HRMS Admin] Step 1/18: GetEmployeeServiceData...", flush=True)
        resp1 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Employee/Info/GetEmployeeServiceData",
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 1 complete (Status: {resp1.status_code})", flush=True)
        
        # Endpoint 2: GetEmployeeLeaveRequests
        print("[HRMS Admin] Step 2/18: GetEmployeeLeaveRequests...", flush=True)
        resp2 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveRequest/GetEmployeeLeaveRequests",
            params={
                "month": 0, "year": 0, "employeeId": employee_id, "leaveTypeId": 0,
                "dayLeaveType": "", "appliedFromDate": "", "appliedToDate": "",
                "stateStatus": "", "pageNumber": 1, "pageSize": 15
            },
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 2 complete (Status: {resp2.status_code})", flush=True)
        
        # Check for already applied leave
        if resp2.status_code == 200:
            try:
                leave_data = resp2.json()
                leave_list = leave_data.get("data") or leave_data.get("result") or []
                for leave in leave_list:
                    leave_from = leave.get("appliedFromDate") or leave.get("AppliedFromDate")
                    leave_to = leave.get("appliedToDate") or leave.get("AppliedToDate")
                    if leave_from and leave_to:
                        leave_from_dt = datetime.strptime(leave_from.split("T")[0], "%Y-%m-%d")
                        leave_to_dt = datetime.strptime(leave_to.split("T")[0], "%Y-%m-%d")
                        # Check for overlap
                        if not (to_dt < leave_from_dt or from_dt > leave_to_dt):
                            print(f"[HRMS Admin] ⚠️  WARNING: Leave already exists for overlapping dates", flush=True)
            except Exception:
                pass  # Continue even if parsing fails
        
        # Endpoint 3: GetLeaveTypesDropdown
        print("[HRMS Admin] Step 3/18: GetLeaveTypesDropdown...", flush=True)
        resp3 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveType/GetLeaveTypesDropdown",
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 3 complete (Status: {resp3.status_code})", flush=True)
        
        # Endpoint 4: GetEmployeeServiceData (again)
        print("[HRMS Admin] Step 4/18: GetEmployeeServiceData (again)...", flush=True)
        resp4 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Employee/Info/GetEmployeeServiceData",
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 4 complete (Status: {resp4.status_code})", flush=True)
        
        # Endpoint 5: GetLeavePeriod
        print("[HRMS Admin] Step 5/18: GetLeavePeriod...", flush=True)
        resp5 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveSetting/GetLeavePeriod",
            params={"employeeId": employee_id},
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 5 complete (Status: {resp5.status_code})", flush=True)
        
        # Endpoint 6: GetLeaveBalance
        print("[HRMS Admin] Step 6/18: GetLeaveBalance...", flush=True)
        resp6 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/EmployeeLeaveBalance/GetLeaveBalance",
            params={"employeeId": employee_id},
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 6 complete (Status: {resp6.status_code})", flush=True)
        
        # Endpoint 7: GetEmployeeLeaveBalancesDropdown
        print("[HRMS Admin] Step 7/18: GetEmployeeLeaveBalancesDropdown...", flush=True)
        resp7 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/EmployeeLeaveBalance/GetEmployeeLeaveBalancesDropdown",
            params={"employeeId": employee_id},
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 7 complete (Status: {resp7.status_code})", flush=True)
        
        # Endpoint 8: GetEmployeeActiveHierarchy (validate hierarchy)
        print("[HRMS Admin] Step 8/18: GetEmployeeActiveHierarchy (validating hierarchy)...", flush=True)
        resp8 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Employee/Hierarchy/GetEmployeeActiveHierarchy",
            params={"id": employee_id},
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 8 complete (Status: {resp8.status_code})", flush=True)
        
        if resp8.status_code != 200:
            return f"❌ Employee {found_name} is not under your hierarchy. You cannot apply leave for this employee."
        
        # Endpoint 9: GetLeaveTypeSetting
        print("[HRMS Admin] Step 9/18: GetLeaveTypeSetting...", flush=True)
        resp9 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveSetting/GetLeaveTypeSetting",
            params={"leaveTypeId": leave_type_id, "employeeId": employee_id},
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 9 complete (Status: {resp9.status_code})", flush=True)
        
        # Endpoint 10: GetTotalRequestDays
        print("[HRMS Admin] Step 10/18: GetTotalRequestDays (calculating days)...", flush=True)
        half_day_param = "Second Portion" if day_leave_type == "Half-Day" else None
        resp10 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveSetting/GetTotalRequestDays",
            params={
                "EmployeeLeaveRequestId": 0,
                "EmployeeId": employee_id,
                "LeaveTypeId": leave_type_id,
                "AppliedFromDate": from_date,
                "AppliedToDate": to_date,
                "halfDayType": half_day_param
            },
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 10 complete (Status: {resp10.status_code})", flush=True)
        
        # Parse days calculation response for warnings
        if resp10.status_code == 200:
            try:
                days_data = resp10.json()
                leave_count_str = days_data.get("leaveCount") or days_data.get("value")
                if leave_count_str:
                    try:
                        api_leave_count = float(leave_count_str)
                        print(f"[HRMS Admin] API calculated working days: {api_leave_count}", flush=True)
                    except (ValueError, TypeError):
                        pass
                
                # Check for warnings in leave list
                leave_list = days_data.get("list")
                if leave_list:
                    try:
                        list_data = json.loads(leave_list) if isinstance(leave_list, str) else leave_list
                        for day_info in list_data:
                            remark = day_info.get("Remarks", "")
                            date = day_info.get("Date", "")
                            if remark == "Already Applied":
                                print(f"[HRMS Admin] ⚠️  WARNING: Leave already applied for {date}", flush=True)
                            elif remark == "Weekend":
                                print(f"[HRMS Admin] ℹ️  INFO: {date} is a weekend", flush=True)
                            elif "Holiday" in remark:
                                print(f"[HRMS Admin] ℹ️  INFO: {date} is a holiday", flush=True)
                    except Exception:
                        pass
            except Exception:
                pass
        
        # Endpoint 11: SaveEmployeeLeaveRequest3 (Submit leave request)
        print("[HRMS Admin] Step 11/18: SaveEmployeeLeaveRequest3 (submitting leave request)...", flush=True)
        
        # Generate LeaveDaysJson
        leave_days_json = _generate_leave_days_json(from_date, total_days)
        
        # Build request body
        request_body = {
            "EmployeeLeaveRequestId": 0,
            "EmployeeLeaveCode": "",
            "EmployeeId": employee_id,
            "UnitId": "",
            "LeaveTypeId": leave_type_id,
            "LeaveTypeName": "",
            "DayLeaveType": day_leave_type,
            "HalfDayType": half_day_type or "",
            "AppliedFromDate": from_date,
            "AppliedToDate": to_date,
            "AppliedTotalDays": total_days,
            "LeavePurpose": reason,
            "EmergencyPhoneNo": "",
            "AddressDuringLeave": "",
            "Remarks": "",
            "LeaveDaysJson": json.dumps(leave_days_json),
            "FilePath": "",
            "Flag": "Submit",
            "EstimatedDeliveryDate": ""
        }
        
        resp11 = httpx.post(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveRequest/SaveEmployeeLeaveRequest3",
            data=request_body,
            headers=headers,
            timeout=30.0,
            verify=False
        )
        
        print(f"[HRMS Admin] ✓ Step 11 complete (Status: {resp11.status_code})", flush=True)
        
        if resp11.status_code != 200:
            error_text = resp11.text[:500] if resp11.text else "No response body"
            return f"❌ Failed to submit leave request. HTTP {resp11.status_code}: {error_text}"
        
        # Parse submission response
        result = resp11.json() if resp11.text else {}
        status = result.get("status", False)
        msg = result.get("msg", "")
        errors = result.get("errors", {})
        
        if not status:
            error_msg = msg or str(errors) or "Unknown error"
            return f"❌ Leave submission failed: {error_msg}"
        
        print(f"[HRMS Admin] ✓ Leave request submitted successfully", flush=True)
        
        # Endpoint 12: GetCompanyHolidayAndEvents
        print("[HRMS Admin] Step 12/18: GetCompanyHolidayAndEvents...", flush=True)
        resp12 = httpx.get(
            f"{HRMS_BASE_URL}/api/hrms/dashboard/CommonDashboard/GetCompanyHolidayAndEvents",
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 12 complete (Status: {resp12.status_code})", flush=True)
        
        # Endpoint 13: GetMyLeaveAppliedRecords
        print("[HRMS Admin] Step 13/18: GetMyLeaveAppliedRecords...", flush=True)
        resp13 = httpx.get(
            f"{HRMS_BASE_URL}/api/hrms/dashboard/LeaveCommonDashboard/GetMyLeaveAppliedRecords",
            params={"pageNumber": 1, "pageSize": 5},
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 13 complete (Status: {resp13.status_code})", flush=True)
        
        # Endpoint 14: GetEmployeesLeaveApproval
        print("[HRMS Admin] Step 14/18: GetEmployeesLeaveApproval...", flush=True)
        resp14 = httpx.get(
            f"{HRMS_BASE_URL}/api/hrms/dashboard/EmployeeLeaveDetails/GetEmployeesLeaveApproval",
            params={"pageSize": 5},
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 14 complete (Status: {resp14.status_code})", flush=True)
        
        # Endpoint 15: GetSubordinatesLeaveApproval
        print("[HRMS Admin] Step 15/18: GetSubordinatesLeaveApproval...", flush=True)
        resp15 = httpx.get(
            f"{HRMS_BASE_URL}/api/hrms/dashboard/SubordinatesLeave/GetSubordinatesLeaveApproval",
            params={"pageNumber": 1, "pageSize": 5},
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 15 complete (Status: {resp15.status_code})", flush=True)
        
        # Endpoint 16: EmployeeLeaveBalancesforSuperviserteam
        print("[HRMS Admin] Step 16/18: EmployeeLeaveBalancesforSuperviserteam...", flush=True)
        resp16 = httpx.post(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/EmployeeLeaveBalance/EmployeeLeaveBalancesforSuperviserteam",
            json={
                "employeeId": employee_id,
                "leaveTypeId": leave_type_id,
                "superviserEmployeeId": 0,
                "pageNumber": 1,
                "pageSize": 15
            },
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 16 complete (Status: {resp16.status_code})", flush=True)
        
        # Endpoint 17: SendLeaveEmail
        print("[HRMS Admin] Step 17/18: SendLeaveEmail...", flush=True)
        
        # Get the response from resp11 (leave apply endpoint) to use as payload
        # Use json= instead of data= to send as JSON with correct Content-Type header
        resp11_json = resp11.json() if resp11.status_code == 200 else {}
        resp17 = httpx.post(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveRequest/SendLeaveEmail",
            json=resp11_json,
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS Admin] ✓ Step 17 complete (Status: {resp17.status_code})", flush=True)
        
        # Endpoint 18: GetEmployeeLeaveRequests (again)
        print("[HRMS Admin] Step 18/18: GetEmployeeLeaveRequests (final check)...", flush=True)
        resp18 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveRequest/GetEmployeeLeaveRequests",
            params={
                "month": 0, "year": 0, "employeeId": employee_id, "leaveTypeId": 0,
                "dayLeaveType": "", "appliedFromDate": "", "appliedToDate": "",
                "stateStatus": "", "pageNumber": 1, "pageSize": 15
            },
            headers=headers, timeout=30.0, verify=False
        )
        print(f"[HRMS Admin] ✓ Step 18 complete (Status: {resp18.status_code})", flush=True)
        
        print("="*70, flush=True)
        print("[HRMS Admin] ✅ LEAVE APPLICATION PROCESS COMPLETED", flush=True)
        print("="*70 + "\n", flush=True)
        
        # Build success message
        success_msg = (
            f"✅ Leave applied successfully for {found_name}!\n"
            f"📅 Period: {from_date} to {to_date} ({total_days} days)\n"
            f"📝 Reason: {reason}"
        )
        if msg:
            success_msg += f"\n💬 Message: {msg}"
        
        return success_msg
        
    except httpx.TimeoutException:
        return "❌ Request timeout. The HRMS system may be slow. Please try again."
    except httpx.RequestError as e:
        return f"❌ Network error during leave application: {str(e)}"
    except Exception as e:
        error_msg = f"❌ Error during leave application: {str(e)}"
        print(f"[HRMS Admin] ❌ EXCEPTION: {str(e)}", flush=True)
        print("="*70 + "\n", flush=True)
        return error_msg
