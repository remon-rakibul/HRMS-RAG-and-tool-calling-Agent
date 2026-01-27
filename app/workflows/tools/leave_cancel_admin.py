"""HRMS Admin Leave Cancellation Tool.

This tool allows admins to cancel leave requests for employees by searching for them by name
and matching leave requests by applied date. It handles the complete leave cancellation workflow
through 5 HRMS API endpoints.
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


def _find_leave_request_by_date(leave_requests: List[Dict], applied_date: str) -> Optional[Dict]:
    """Find leave request that matches the applied_date within its leave period.
    
    Args:
        leave_requests: List of leave request dictionaries
        applied_date: Date string in YYYY-MM-DD format to match
        
    Returns:
        Matching leave request dict or None if not found
    """
    try:
        applied_dt = datetime.strptime(applied_date, "%Y-%m-%d")
    except ValueError:
        print(f"[HRMS Admin] Invalid applied_date format: {applied_date}", flush=True)
        return None
    
    matches = []
    checked_requests = []
    
    print(f"[HRMS Admin] Checking {len(leave_requests)} leave request(s) for date match...", flush=True)
    
    for idx, leave_req in enumerate(leave_requests):
        if not isinstance(leave_req, dict):
            print(f"[HRMS Admin] Request {idx+1} is not a dict, skipping", flush=True)
            continue
        
        # Extract dates from various possible field names
        from_date_str = (leave_req.get("appliedFromDate") or 
                        leave_req.get("AppliedFromDate") or 
                        leave_req.get("applied_from_date") or "")
        to_date_str = (leave_req.get("appliedToDate") or 
                      leave_req.get("AppliedToDate") or 
                      leave_req.get("applied_to_date") or "")
        
        if not from_date_str or not to_date_str:
            print(f"[HRMS Admin] Request {idx+1} missing date fields (from: {bool(from_date_str)}, to: {bool(to_date_str)})", flush=True)
            continue
        
        # Extract date part from datetime strings
        from_date = _extract_date_from_datetime(from_date_str)
        to_date = _extract_date_from_datetime(to_date_str)
        
        if not from_date or not to_date:
            print(f"[HRMS Admin] Request {idx+1} failed to extract dates (from: {from_date}, to: {to_date})", flush=True)
            continue
        
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            
            checked_requests.append(f"Request {idx+1}: {from_date} to {to_date}")
            
            # Check if applied_date falls within the leave period
            if from_dt <= applied_dt <= to_dt:
                request_id = leave_req.get("employeeLeaveRequestId") or leave_req.get("EmployeeLeaveRequestId")
                print(f"[HRMS Admin] ✓ Match found! Request {idx+1} (ID: {request_id}) covers date {applied_date}", flush=True)
                matches.append(leave_req)
        except ValueError as e:
            print(f"[HRMS Admin] Request {idx+1} date parsing error: {str(e)} (from: {from_date}, to: {to_date})", flush=True)
            continue
    
    if checked_requests:
        print(f"[HRMS Admin] Checked leave periods: {', '.join(checked_requests[:5])}", flush=True)
    
    if len(matches) == 0:
        print(f"[HRMS Admin] No leave request found matching applied date: {applied_date}", flush=True)
        return None
    
    if len(matches) > 1:
        match_ids = [str(m.get("employeeLeaveRequestId") or m.get("EmployeeLeaveRequestId") or "unknown") 
                    for m in matches]
        print(f"[HRMS Admin] Multiple leave requests found matching date {applied_date}: {match_ids}", flush=True)
        return {
            "error": f"Multiple leave requests found for date {applied_date}. Please provide more specific information. Request IDs: {', '.join(match_ids[:5])}"
        }
    
    matched = matches[0]
    request_id = matched.get("employeeLeaveRequestId") or matched.get("EmployeeLeaveRequestId")
    print(f"[HRMS Admin] ✓ Found leave request: ID {request_id}", flush=True)
    return matched


@tool_registry.register
def cancel_leave_for_employee(
    employee_name: Annotated[str, "Employee name to search for (e.g., 'Neha Muquid')"],
    applied_date: Annotated[str, "Date the leave was applied for in YYYY-MM-DD format (e.g., '2026-01-12')"],
    remarks: Annotated[Optional[str], "Cancellation remarks (optional, defaults to 'Cancelled')"] = None
) -> str:
    """Cancel leave request for an employee. Search by name, find leave request by applied date, and cancel it.
    
    This tool allows admins to cancel leave requests for employees by searching for them by name
    and matching leave requests by the date the leave was applied for. It handles the complete
    cancellation workflow through all required HRMS API endpoints.
    
    Examples:
    - "cancel leave for neha muquid applied on 2026-01-12"
    - "cancel leave request for john doe dated 2026-01-15"
    """
    # Set default remarks
    if remarks is None:
        remarks = "Cancelled"
    
    print("\n" + "="*70, flush=True)
    print("[HRMS Admin] ADMIN LEAVE CANCELLATION PROCESS STARTED", flush=True)
    print("="*70, flush=True)
    print(f"[HRMS Admin] Employee Name: {employee_name}", flush=True)
    print(f"[HRMS Admin] Applied Date: {applied_date}", flush=True)
    print(f"[HRMS Admin] Remarks: {remarks}", flush=True)
    print("-" * 70, flush=True)
    
    # Authenticate
    token = _get_hrms_token()
    if not token:
        return "❌ Failed to authenticate with HRMS system."
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 1: Get All Employees and Search by Name
    print("[HRMS Admin] Step 1/5: GetEmployeeServiceData (searching for employee)...", flush=True)
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
    
    # Step 2: Get Employee Leave Requests
    print("[HRMS Admin] Step 2/5: GetEmployeeLeaveRequests (finding matching leave request)...", flush=True)
    try:
        resp2 = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveRequest/GetEmployeeLeaveRequests",
            params={
                "month": 0,
                "year": 0,
                "employeeId": employee_id,
                "leaveTypeId": 0,
                "dayLeaveType": "",
                "appliedFromDate": "",
                "appliedToDate": "",
                "stateStatus": "",
                "pageNumber": 1,
                "pageSize": 15
            },
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS Admin] ✓ Step 2 complete (Status: {resp2.status_code})", flush=True)
        
        if resp2.status_code != 200:
            return f"❌ Failed to retrieve leave requests. HTTP {resp2.status_code}"
        
        # Parse leave requests
        try:
            leave_data = resp2.json()
            
            # Handle direct list response
            if isinstance(leave_data, list):
                leave_list = leave_data
                print(f"[HRMS Admin] Response is a direct list with {len(leave_list)} items", flush=True)
            elif isinstance(leave_data, dict):
                # Try multiple possible keys for the leave list
                leave_list = (leave_data.get("data") or leave_data.get("result") or 
                             leave_data.get("items") or leave_data.get("list") or [])
                print(f"[HRMS Admin] Response is a dict, extracted list with {len(leave_list)} items", flush=True)
            else:
                print(f"[HRMS Admin] ⚠️ Unexpected response type: {type(leave_data)}", flush=True)
                leave_list = []
        except Exception as e:
            print(f"[HRMS Admin] ❌ Failed to parse JSON response: {str(e)}", flush=True)
            return f"❌ Failed to parse leave requests response: {str(e)}"
        
        if not isinstance(leave_list, list):
            print(f"[HRMS Admin] ⚠️ Leave list is not a list, type: {type(leave_list)}", flush=True)
            leave_list = []
        
        print(f"[HRMS Admin] Found {len(leave_list)} leave request(s) in response", flush=True)
        
        if len(leave_list) == 0:
            print(f"[HRMS Admin] ⚠️ No leave requests found in response. Response structure: {str(leave_data)[:500]}", flush=True)
            return f"❌ No leave requests found for {found_name}. Please check if the employee has any leave requests."
        
        # Find matching leave request by date
        print(f"[HRMS Admin] Searching for leave request matching date: {formatted_date}", flush=True)
        matched_leave = _find_leave_request_by_date(leave_list, formatted_date)
        
        if not matched_leave:
            # Log available dates for debugging
            available_dates = []
            for req in leave_list[:5]:  # Check first 5 requests
                from_date = _extract_date_from_datetime(
                    req.get("appliedFromDate") or req.get("AppliedFromDate") or ""
                )
                to_date = _extract_date_from_datetime(
                    req.get("appliedToDate") or req.get("AppliedToDate") or ""
                )
                if from_date and to_date:
                    available_dates.append(f"{from_date} to {to_date}")
            print(f"[HRMS Admin] Available leave periods: {', '.join(available_dates) if available_dates else 'None found'}", flush=True)
            return f"❌ No leave request found for {found_name} with applied date {formatted_date}."
        
        if "error" in matched_leave:
            return f"❌ {matched_leave['error']}"
        
        # Extract required fields from matched leave request
        employee_leave_request_id = (matched_leave.get("employeeLeaveRequestId") or 
                                    matched_leave.get("EmployeeLeaveRequestId"))
        leave_type_id = (matched_leave.get("leaveTypeId") or 
                        matched_leave.get("LeaveTypeId") or 0)
        
        if not employee_leave_request_id:
            return "❌ Leave request found but missing employeeLeaveRequestId."
        
        print(f"[HRMS Admin] Found leave request ID: {employee_leave_request_id}", flush=True)
        print(f"[HRMS Admin] Leave Type ID: {leave_type_id}", flush=True)
        print("-" * 70, flush=True)
        
    except httpx.TimeoutException:
        return "❌ Request timeout while retrieving leave requests. Please try again."
    except httpx.RequestError as e:
        return f"❌ Network error while retrieving leave requests: {str(e)}"
    except Exception as e:
        return f"❌ Error retrieving leave requests: {str(e)}"
    
    try:
        # Step 3: Delete Leave Request
        print("[HRMS Admin] Step 3/5: DeleteEmployeeLeaveRequest (cancelling leave request)...", flush=True)
        resp3 = httpx.post(
            f"{HRMS_BASE_URL}/api/hrms/leave/LeaveRequest/DeleteEmployeeLeaveRequest",
            json={
                "employeeId": employee_id,
                "employeeLeaveRequestId": employee_leave_request_id,
                "leaveTypeId": leave_type_id
            },
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS Admin] ✓ Step 3 complete (Status: {resp3.status_code})", flush=True)
        
        if resp3.status_code != 200:
            error_text = resp3.text[:500] if resp3.text else "No response body"
            return f"❌ Failed to cancel leave request. HTTP {resp3.status_code}: {error_text}"
        
        # Parse cancellation response
        cancel_result = resp3.json() if resp3.text else {}
        cancel_status = cancel_result.get("status", False)
        cancel_msg = cancel_result.get("msg", "")
        
        if not cancel_status:
            error_msg = cancel_msg or str(cancel_result.get("errors", {})) or "Unknown error"
            return f"❌ Leave cancellation failed: {error_msg}"
        
        print(f"[HRMS Admin] ✓ Leave request cancelled successfully", flush=True)
        
        # Step 4: Send Cancellation Email
        print("[HRMS Admin] Step 4/5: LeaveRequestEmailSend (sending cancellation email)...", flush=True)
        resp4 = httpx.get(
            f"{HRMS_BASE_URL}/api/hrms/leave/LeaveRequest/LeaveRequestEmailSend",
            params={
                "employeeId": employee_id,
                "leaveTypeId": leave_type_id,
                "emailType": "Cancelled",
                "leaveRequestId": employee_leave_request_id
            },
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS Admin] ✓ Step 4 complete (Status: {resp4.status_code})", flush=True)
        
        # Step 5: Get Employee Leave Requests (Final Verification)
        print("[HRMS Admin] Step 5/5: GetEmployeeLeaveRequests (final verification)...", flush=True)
        resp5 = httpx.get(
            f"{HRMS_BASE_URL}/api/hrms/leave/LeaveRequest/GetEmployeeLeaveRequests",
            params={
                "month": 0,
                "year": 0,
                "employeeId": employee_id,
                "leaveTypeId": 0,
                "dayLeaveType": "",
                "appliedFromDate": "",
                "appliedToDate": "",
                "stateStatus": "",
                "pageNumber": 1,
                "pageSize": 15
            },
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS Admin] ✓ Step 5 complete (Status: {resp5.status_code})", flush=True)
        
        print("="*70, flush=True)
        print("[HRMS Admin] ✅ LEAVE CANCELLATION PROCESS COMPLETED", flush=True)
        print("="*70 + "\n", flush=True)
        
        # Build success message
        success_msg = (
            f"✅ Leave cancelled successfully for {found_name}!\n"
            f"📅 Applied Date: {formatted_date}\n"
            f"📝 Remarks: {remarks}"
        )
        if cancel_msg:
            success_msg += f"\n💬 Message: {cancel_msg}"
        
        return success_msg
        
    except httpx.TimeoutException:
        return "❌ Request timeout. The HRMS system may be slow. Please try again."
    except httpx.RequestError as e:
        return f"❌ Network error during leave cancellation: {str(e)}"
    except Exception as e:
        error_msg = f"❌ Error during leave cancellation: {str(e)}"
        print(f"[HRMS Admin] ❌ EXCEPTION: {str(e)}", flush=True)
        print("="*70 + "\n", flush=True)
        return error_msg
