"""HRMS Admin Attendance Approval Tool.

This tool allows admins to approve manual attendance requests for employees by searching for them by name
and matching attendance requests by applied date and time request type. It handles the complete attendance
approval workflow through 6 HRMS API endpoints.
"""

from typing import Annotated, Optional, Dict, Any, List
from datetime import datetime
import httpx
import urllib3
import json
from app.workflows.tools import tool_registry

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# HRMS API Configuration - Admin credentials for API authentication
HRMS_BASE_URL = "https://abcl.myrecombd.com:9999"
HRMS_USERNAME = "demo_admin"
HRMS_PASSWORD = "Demo@2024"


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


def _extract_date_from_datetime(datetime_str: str) -> str:
    """Extract date part from ISO datetime string."""
    if not datetime_str:
        return ""
    
    # Handle ISO datetime format (e.g., "2026-01-12T00:00:00")
    if "T" in datetime_str:
        return datetime_str.split("T")[0]
    
    # Handle date-only strings
    return datetime_str[:10] if len(datetime_str) >= 10 else datetime_str


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


def _normalize_time_request(time_request: str) -> str:
    """Normalize time request input to API format.
    
    Args:
        time_request: User input like "intime", "outtime", "both", etc.
        
    Returns:
        Normalized value: "In-Time", "Out-Time", or "Both"
    """
    time_lower = time_request.lower().strip()
    
    if time_lower in ["both", "both times", "all", "in and out", "in-out"]:
        return "Both"
    elif time_lower in ["in-time", "in time", "intime", "in", "entry", "entry time"]:
        return "In-Time"
    elif time_lower in ["out-time", "out time", "outtime", "out", "exit", "exit time"]:
        return "Out-Time"
    else:
        # Default to what was provided if not recognized
        return time_request


def _find_attendance_request_by_date_and_time(
    attendance_requests: List[Dict], 
    applied_date: str, 
    time_request_for: str
) -> Optional[Dict]:
    """Find attendance request that matches the applied_date and timeRequestFor.
    
    Args:
        attendance_requests: List of attendance request dictionaries
        applied_date: Date string in YYYY-MM-DD format to match
        time_request_for: Time request type: "In-Time", "Out-Time", or "Both"
        
    Returns:
        Matching attendance request dict or None if not found
    """
    try:
        applied_dt = datetime.strptime(applied_date, "%Y-%m-%d")
    except ValueError:
        print(f"[HRMS Admin] Invalid applied_date format: {applied_date}", flush=True)
        return None
    
    # Normalize time_request_for
    normalized_time = _normalize_time_request(time_request_for)
    
    matches = []
    checked_requests = []
    
    print(f"[HRMS Admin] Checking {len(attendance_requests)} attendance request(s) for date and time match...", flush=True)
    print(f"[HRMS Admin] Looking for: date={applied_date}, timeRequestFor={normalized_time}", flush=True)
    
    for idx, att_req in enumerate(attendance_requests):
        if not isinstance(att_req, dict):
            print(f"[HRMS Admin] Request {idx+1} is not a dict, skipping", flush=True)
            continue
        
        # Extract date from various possible field names
        attendance_date_str = (att_req.get("attendanceDate") or 
                              att_req.get("AttendanceDate") or 
                              att_req.get("attendance_date") or "")
        
        if not attendance_date_str:
            print(f"[HRMS Admin] Request {idx+1} missing attendanceDate field", flush=True)
            continue
        
        # Extract date part from datetime strings
        attendance_date = _extract_date_from_datetime(attendance_date_str)
        
        if not attendance_date:
            print(f"[HRMS Admin] Request {idx+1} failed to extract date (date: {attendance_date_str})", flush=True)
            continue
        
        # Extract timeRequestFor from various possible field names
        req_time_for = (att_req.get("timeRequestFor") or 
                       att_req.get("TimeRequestFor") or 
                       att_req.get("time_request_for") or "")
        
        if not req_time_for:
            print(f"[HRMS Admin] Request {idx+1} missing timeRequestFor field", flush=True)
            continue
        
        # Normalize the timeRequestFor from API response
        normalized_req_time = _normalize_time_request(req_time_for)
        
        try:
            att_dt = datetime.strptime(attendance_date, "%Y-%m-%d")
            
            checked_requests.append(f"Request {idx+1}: date={attendance_date}, timeRequestFor={normalized_req_time}")
            
            # Check if date matches AND timeRequestFor matches
            if att_dt == applied_dt and normalized_req_time == normalized_time:
                request_id = att_req.get("manualAttendanceId") or att_req.get("ManualAttendanceId")
                print(f"[HRMS Admin] ✓ Match found! Request {idx+1} (ID: {request_id}) matches date {applied_date} and timeRequestFor {normalized_time}", flush=True)
                matches.append(att_req)
        except ValueError as e:
            print(f"[HRMS Admin] Request {idx+1} date parsing error: {str(e)} (date: {attendance_date})", flush=True)
            continue
    
    if checked_requests:
        print(f"[HRMS Admin] Checked attendance requests: {', '.join(checked_requests[:5])}", flush=True)
    
    if len(matches) == 0:
        print(f"[HRMS Admin] No attendance request found matching date {applied_date} and timeRequestFor {normalized_time}", flush=True)
        return None
    
    if len(matches) > 1:
        match_ids = [str(m.get("manualAttendanceId") or m.get("ManualAttendanceId") or "unknown") 
                    for m in matches]
        print(f"[HRMS Admin] Multiple attendance requests found matching date {applied_date} and timeRequestFor {normalized_time}: {match_ids}", flush=True)
        return {
            "error": f"Multiple attendance requests found for date {applied_date} and timeRequestFor {normalized_time}. Please provide more specific information. Request IDs: {', '.join(match_ids[:5])}"
        }
    
    matched = matches[0]
    request_id = matched.get("manualAttendanceId") or matched.get("ManualAttendanceId")
    print(f"[HRMS Admin] ✓ Found attendance request: ID {request_id}", flush=True)
    return matched


@tool_registry.register
def approve_attendance_for_employee(
    employee_name: Annotated[str, "Employee name to search for (e.g., 'Neha Muquid')"],
    applied_date: Annotated[str, "Date the attendance was applied for in YYYY-MM-DD format (e.g., '2026-01-12')"],
    requested_time: Annotated[str, "Time request type: 'In-Time', 'Out-Time', or 'Both' (can also accept 'intime', 'outtime', 'both')"],
    remarks: Annotated[Optional[str], "Approval remarks (optional, defaults to 'Approved')"] = None
) -> str:
    """Approve manual attendance request for an employee. Search by name, find attendance request by applied date and time type, and approve it.
    
    This tool allows admins to approve manual attendance requests for employees by searching for them by name
    and matching attendance requests by the date and time request type. It handles the complete
    approval workflow through all required HRMS API endpoints.
    
    Examples:
    - "approve attendance for neha muquid applied on 2026-01-12 for in-time"
    - "approve attendance request for john doe dated 2026-01-15 for both times"
    """
    # Set default remarks
    if remarks is None:
        remarks = "Approved"
    
    # Normalize requested_time
    normalized_time = _normalize_time_request(requested_time)
    
    print("\n" + "="*70, flush=True)
    print("[HRMS Admin] ADMIN ATTENDANCE APPROVAL PROCESS STARTED", flush=True)
    print("="*70, flush=True)
    print(f"[HRMS Admin] Employee Name: {employee_name}", flush=True)
    print(f"[HRMS Admin] Applied Date: {applied_date}", flush=True)
    print(f"[HRMS Admin] Requested Time: {requested_time} -> {normalized_time}", flush=True)
    print(f"[HRMS Admin] Remarks: {remarks}", flush=True)
    print("-" * 70, flush=True)
    
    # Authenticate
    token = _get_hrms_token()
    if not token:
        return "❌ Failed to authenticate with HRMS system."
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 1: Get All Employees and Search by Name
    print("[HRMS Admin] Step 1/6: GetEmployeeServiceData (searching for employee)...", flush=True)
    emp_result = _search_employee_by_name(token, employee_name)
    if not emp_result:
        return f"❌ No employee found matching '{employee_name}'. Please check the name and try again."
    
    if "error" in emp_result:
        return f"❌ {emp_result['error']}"
    
    employee_id = emp_result["employeeId"]
    found_name = emp_result["employeeName"]
    
    print(f"[HRMS Admin] Using Employee ID: {employee_id}", flush=True)
    print("-" * 70, flush=True)
    
    # Format applied_date
    formatted_date = _format_datetime(applied_date)
    try:
        applied_dt = datetime.strptime(formatted_date, "%Y-%m-%d")
        formatted_date = applied_dt.strftime("%Y-%m-%d")
    except ValueError:
        return f"❌ Invalid date format: {applied_date}. Please use YYYY-MM-DD format."
    
    # Step 2: Get Employee Manual Attendances
    print("[HRMS Admin] Step 2/6: GetEmployeeManualAttendances (finding matching attendance request)...", flush=True)
    try:
        resp2 = httpx.get(
            f"{HRMS_BASE_URL}/api/hrms/Attendance/ManualAttendance/GetEmployeeManualAttendances",
            params={
                "employeeId": employee_id,
                "pageSize": 15,
                "pageNumber": 1
            },
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS Admin] ✓ Step 2 complete (Status: {resp2.status_code})", flush=True)
        
        if resp2.status_code != 200:
            return f"❌ Failed to retrieve attendance requests. HTTP {resp2.status_code}"
        
        # Parse attendance requests
        try:
            attendance_data = resp2.json()
            
            # Handle direct list response
            if isinstance(attendance_data, list):
                attendance_list = attendance_data
                print(f"[HRMS Admin] Response is a direct list with {len(attendance_list)} items", flush=True)
            elif isinstance(attendance_data, dict):
                # Try multiple possible keys for the attendance list
                attendance_list = (attendance_data.get("data") or attendance_data.get("result") or 
                                 attendance_data.get("items") or attendance_data.get("list") or [])
                print(f"[HRMS Admin] Response is a dict, extracted list with {len(attendance_list)} items", flush=True)
            else:
                print(f"[HRMS Admin] ⚠️ Unexpected response type: {type(attendance_data)}", flush=True)
                attendance_list = []
        except Exception as e:
            print(f"[HRMS Admin] ❌ Failed to parse JSON response: {str(e)}", flush=True)
            return f"❌ Failed to parse attendance requests response: {str(e)}"
        
        if not isinstance(attendance_list, list):
            print(f"[HRMS Admin] ⚠️ Attendance list is not a list, type: {type(attendance_list)}", flush=True)
            attendance_list = []
        
        print(f"[HRMS Admin] Found {len(attendance_list)} attendance request(s) in response", flush=True)
        
        if len(attendance_list) == 0:
            print(f"[HRMS Admin] ⚠️ No attendance requests found in response. Response structure: {str(attendance_data)[:500]}", flush=True)
            return f"❌ No attendance requests found for {found_name}. Please check if the employee has any pending attendance requests."
        
        # Find matching attendance request by date and timeRequestFor
        print(f"[HRMS Admin] Searching for attendance request matching date: {formatted_date}, timeRequestFor: {normalized_time}", flush=True)
        matched_attendance = _find_attendance_request_by_date_and_time(attendance_list, formatted_date, normalized_time)
        
        if not matched_attendance:
            # Log available dates for debugging
            available_requests = []
            for req in attendance_list[:5]:  # Check first 5 requests
                req_date = _extract_date_from_datetime(
                    req.get("attendanceDate") or req.get("AttendanceDate") or ""
                )
                req_time = req.get("timeRequestFor") or req.get("TimeRequestFor") or ""
                if req_date and req_time:
                    available_requests.append(f"date={req_date}, timeRequestFor={req_time}")
            print(f"[HRMS Admin] Available attendance requests: {', '.join(available_requests) if available_requests else 'None found'}", flush=True)
            return f"❌ No attendance request found for {found_name} with applied date {formatted_date} and timeRequestFor {normalized_time}."
        
        if "error" in matched_attendance:
            return f"❌ {matched_attendance['error']}"
        
        # Extract required fields from matched attendance request
        manual_attendance_id = (matched_attendance.get("manualAttendanceId") or 
                               matched_attendance.get("ManualAttendanceId"))
        
        if not manual_attendance_id:
            return "❌ Attendance request found but missing manualAttendanceId."
        
        print(f"[HRMS Admin] Found attendance request ID: {manual_attendance_id}", flush=True)
        print("-" * 70, flush=True)
        
    except httpx.TimeoutException:
        return "❌ Request timeout while retrieving attendance requests. Please try again."
    except httpx.RequestError as e:
        return f"❌ Network error while retrieving attendance requests: {str(e)}"
    except Exception as e:
        return f"❌ Error retrieving attendance requests: {str(e)}"
    
    try:
        # Step 3: Get Employee Manual Attendance by ID
        print("[HRMS Admin] Step 3/6: GetEmployeeManualAttendances (by ID)...", flush=True)
        resp3 = httpx.get(
            f"{HRMS_BASE_URL}/api/hrms/Attendance/ManualAttendance/GetEmployeeManualAttendances",
            params={
                "manualAttendanceId": manual_attendance_id
            },
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS Admin] ✓ Step 3 complete (Status: {resp3.status_code})", flush=True)
        
        # Step 4: Approve Manual Attendance
        print("[HRMS Admin] Step 4/6: ApprovalRequest (approving attendance request)...", flush=True)
        resp4 = httpx.post(
            f"{HRMS_BASE_URL}/api/hrms/Attendance/ManualAttendance/ApprovalRequest",
            json={
                "manualAttendanceId": manual_attendance_id,
                "remarks": remarks,
                "stateStatus": "Approved"
            },
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS Admin] ✓ Step 4 complete (Status: {resp4.status_code})", flush=True)
        
        if resp4.status_code != 200:
            error_text = resp4.text[:500] if resp4.text else "No response body"
            return f"❌ Failed to approve attendance request. HTTP {resp4.status_code}: {error_text}"
        
        # Parse approval response
        approval_result = resp4.json() if resp4.text else {}
        approval_status = approval_result.get("status", False)
        approval_msg = approval_result.get("msg", "")
        
        if not approval_status:
            error_msg = approval_msg or str(approval_result.get("errors", {})) or "Unknown error"
            return f"❌ Attendance approval failed: {error_msg}"
        
        print(f"[HRMS Admin] ✓ Attendance request approved successfully", flush=True)
        
        # Step 5: Send Email
        print("[HRMS Admin] Step 5/6: SendEmail (sending approval email)...", flush=True)
        resp5 = httpx.post(
            f"{HRMS_BASE_URL}/api/hrms/Attendance/ManualAttendance/SendEmail",
            json=approval_result,  # Use response from Step 4
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS Admin] ✓ Step 5 complete (Status: {resp5.status_code})", flush=True)
        
        # Step 6: Get Subordinates Manual Attendances Requests (Final Verification)
        print("[HRMS Admin] Step 6/6: GetSubordinatesManualAttendancesRequests (final verification)...", flush=True)
        resp6 = httpx.get(
            f"{HRMS_BASE_URL}/api/hrms/Attendance/ManualAttendance/GetSubordinatesManualAttendancesRequests",
            params={
                "timeRequestFor": "",
                "stateStatus": "",
                "reason": "",
                "employeeId": 0,
                "pageSize": 15,
                "pageNumber": 1
            },
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS Admin] ✓ Step 6 complete (Status: {resp6.status_code})", flush=True)
        
        print("="*70, flush=True)
        print("[HRMS Admin] ✅ ATTENDANCE APPROVAL PROCESS COMPLETED", flush=True)
        print("="*70 + "\n", flush=True)
        
        # Build success message
        success_msg = (
            f"✅ Attendance approved successfully for {found_name}!\n"
            f"📅 Applied Date: {formatted_date}\n"
            f"⏰ Time Request: {normalized_time}\n"
            f"📝 Remarks: {remarks}"
        )
        if approval_msg:
            success_msg += f"\n💬 Message: {approval_msg}"
        
        return success_msg
        
    except httpx.TimeoutException:
        return "❌ Request timeout. The HRMS system may be slow. Please try again."
    except httpx.RequestError as e:
        return f"❌ Network error during attendance approval: {str(e)}"
    except Exception as e:
        error_msg = f"❌ Error during attendance approval: {str(e)}"
        print(f"[HRMS Admin] ❌ EXCEPTION: {str(e)}", flush=True)
        print("="*70 + "\n", flush=True)
        return error_msg
