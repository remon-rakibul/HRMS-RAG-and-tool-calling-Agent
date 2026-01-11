"""HRMS Leave Application Tool.

This tool allows users to apply for leave through the HRMS API.
It handles the complete leave application workflow:
1. Authenticate with admin credentials
2. Fetch leave balance
3. Fetch leave period settings
4. Fetch leave types dropdown
5. Get employee mobile number
6. Get employee address
7. Calculate total request days
8. Submit complete leave request
"""

from typing import Annotated, Optional, Dict, Any, List
from datetime import datetime, timedelta
import httpx
import urllib3
import json
from app.workflows.tools import tool_registry
from app.workflows.context import get_employee_id

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# HRMS API Configuration - Admin credentials for API authentication
HRMS_BASE_URL = "https://abcl.myrecombd.com:9999"
HRMS_USERNAME = "demo_admin"
HRMS_PASSWORD = "Demo@2024"

# Default values (can be overridden)
DEFAULT_EMPLOYEE_ID = 335  # Fallback if no context available
DEFAULT_LEAVE_TYPE_ID = 2  # Sick Leave (most common, widely available)
DEFAULT_UNIT_ID = None


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
            print(f"[HRMS] Encrypt failed: HTTP {response.status_code}", flush=True)
            return None
    except Exception as e:
        print(f"[HRMS] Encrypt error: {str(e)}", flush=True)
        return None


def _get_hrms_token() -> Optional[str]:
    """Authenticate with HRMS and get bearer token."""
    print("[HRMS] Authenticating...", flush=True)
    
    # Encrypt credentials
    encrypted_username = _encrypt_value(HRMS_USERNAME)
    encrypted_password = _encrypt_value(HRMS_PASSWORD)
    
    if not encrypted_username or not encrypted_password:
        print("[HRMS] Failed to encrypt credentials", flush=True)
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
                print("[HRMS] Authentication successful", flush=True)
                return token
            
        print(f"[HRMS] Login failed: {login_response.status_code}", flush=True)
        return None
            
    except Exception as e:
        print(f"[HRMS] Login error: {str(e)}", flush=True)
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


@tool_registry.register
def apply_for_leave(
    start_date: Annotated[str, "Leave start date in YYYY-MM-DD format (e.g., '2024-12-01')"],
    total_days: Annotated[int, "Total number of leave days (e.g., 1, 2, 3)"],
    reason: Annotated[str, "Reason or purpose for the leave application"],
    employee_id: Annotated[Optional[int], "Employee ID (optional, defaults to logged-in user)"] = None,
    leave_type_id: Annotated[Optional[int], "Leave type ID: 1=Annual, 2=Casual, 3=Sick (optional, defaults to 2)"] = None,
    day_leave_type: Annotated[Optional[str], "Leave duration: 'Full-Day' or 'Half-Day' (optional, defaults to Full-Day)"] = None,
    half_day_type: Annotated[Optional[str], "If Half-Day, specify: 'First-Half' or 'Second-Half' (optional)"] = None
) -> str:
    """Apply for leave in the HRMS system. Use this when the user wants to request time off, apply for leave, take vacation, or needs days off from work.
    
    This tool handles the complete leave application workflow including validation.
    
    Examples:
    - "Apply for 3 days leave starting December 1st for vacation"
    - "I need sick leave for 2 days from tomorrow"
    - "Request half day leave on Friday afternoon"
    """
    # Set defaults for optional parameters
    # Try to get employee_id from context first, then use parameter, then fallback to default
    if employee_id is None:
        employee_id = get_employee_id()  # Get from context set by chat service
        if employee_id is None:
            employee_id = DEFAULT_EMPLOYEE_ID  # Final fallback
            print(f"[HRMS] Warning: Using default employee_id={employee_id}", flush=True)
        else:
            print(f"[HRMS] Using employee_id from context: {employee_id}", flush=True)
    else:
        print(f"[HRMS] Using employee_id from parameter: {employee_id}", flush=True)
    
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
    
    unit_id = DEFAULT_UNIT_ID
    
    print("\n" + "="*70, flush=True)
    print("[HRMS] LEAVE APPLICATION PROCESS STARTED", flush=True)
    print("="*70, flush=True)
    
    # Format dates
    from_date = _format_datetime(start_date)
    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    to_dt = from_dt + timedelta(days=total_days - 1)
    to_date = to_dt.strftime("%Y-%m-%d")
    
    print(f"[HRMS] Employee ID: {employee_id}", flush=True)
    print(f"[HRMS] Leave Type ID: {leave_type_id}", flush=True)
    print(f"[HRMS] Day Type: {day_leave_type}" + (f" ({half_day_type})" if half_day_type else ""), flush=True)
    print(f"[HRMS] Leave Period: {from_date} to {to_date} ({total_days} days)", flush=True)
    print(f"[HRMS] Reason: {reason}", flush=True)
    print("-" * 70, flush=True)
    
    # Step 1: Authenticate
    token = _get_hrms_token()
    if not token:
        return "❌ Failed to authenticate with HRMS system."
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Step 2: Get Leave Balance
        print("[HRMS] Step 1/6: Fetching leave balance...", flush=True)
        balance_response = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/EmployeeLeaveBalance/GetLeaveBalance",
            params={"employeeId": employee_id},
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS] ✓ Leave balance fetched (Status: {balance_response.status_code})", flush=True)
        print(f"[HRMS] DEBUG - Balance Response Body:", flush=True)
        print(balance_response.text[:1000], flush=True)  # First 1000 chars
        print("-" * 40, flush=True)
        
        # Step 3: Get Leave Period
        print("[HRMS] Step 2/6: Fetching leave period settings...", flush=True)
        period_response = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveSetting/GetLeavePeriod",
            params={"employeeId": employee_id},
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS] ✓ Leave period fetched (Status: {period_response.status_code})", flush=True)
        print(f"[HRMS] DEBUG - Period Response Body:", flush=True)
        print(period_response.text[:1000], flush=True)
        print("-" * 40, flush=True)
        
        # Step 4: Get Leave Types Dropdown
        print("[HRMS] Step 3/6: Fetching leave types...", flush=True)
        types_response = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/EmployeeLeaveBalance/GetEmployeeLeaveBalancesDropdown",
            params={"employeeId": employee_id},
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS] ✓ Leave types fetched (Status: {types_response.status_code})", flush=True)
        print(f"[HRMS] DEBUG - Leave Types Response Body:", flush=True)
        print(types_response.text[:1000], flush=True)
        print("-" * 40, flush=True)
        
        # Step 5: Get Mobile Number
        print("[HRMS] Step 4/6: Fetching employee mobile number...", flush=True)
        mobile_response = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Employee/Info/GetEmployeePersonalMobileNumberByEmployeeId",
            params={"id": employee_id},
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS] Mobile Response (Status: {mobile_response.status_code}):", flush=True)
        print(f"[HRMS] DEBUG - Mobile Response Body:", flush=True)
        print(repr(mobile_response.text[:500]), flush=True)  # Use repr to see exact characters
        print("-" * 40, flush=True)
        
        emergency_phone = None
        if mobile_response.status_code == 200:
            # API returns plain text, not JSON - parse directly
            text = mobile_response.text.strip().strip('"').strip("'")
            if text and len(text) > 5:  # Sanity check for phone number
                emergency_phone = text
            else:
                # Try JSON parsing as fallback (in case API format changes)
                try:
                    mobile_data = mobile_response.json()
                    emergency_phone = mobile_data.get("value") or mobile_data.get("mobileNumber")
                except Exception:
                    pass  # Already tried plain text, JSON failed too
        
        if not emergency_phone:
            error_msg = f"❌ Failed to fetch mobile number for employee {employee_id}. API returned status {mobile_response.status_code}."
            print(f"[HRMS] ❌ {error_msg}", flush=True)
            return error_msg
        
        print(f"[HRMS] ✓ Mobile number: {emergency_phone}", flush=True)
        
        # Step 6: Get Address
        print("[HRMS] Step 5/6: Fetching employee address...", flush=True)
        address_response = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Employee/Info/GetEmployeePresentAddressByEmployeeId",
            params={"id": employee_id},
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS] Address Response (Status: {address_response.status_code}):", flush=True)
        print(f"[HRMS] DEBUG - Address Response Body:", flush=True)
        print(repr(address_response.text[:500]), flush=True)
        print("-" * 40, flush=True)
        
        address = None
        if address_response.status_code == 200:
            # API returns plain text, not JSON - parse directly
            text = address_response.text.strip().strip('"').strip("'")
            if text and len(text) > 3:  # Sanity check
                address = text
            else:
                # Try JSON parsing as fallback (in case API format changes)
                try:
                    address_data = address_response.json()
                    address = address_data.get("value") or address_data.get("address")
                except Exception:
                    pass  # Already tried plain text, JSON failed too
        
        if not address:
            error_msg = f"❌ Failed to fetch address for employee {employee_id}. API returned status {address_response.status_code}."
            print(f"[HRMS] ❌ {error_msg}", flush=True)
            return error_msg
        
        print(f"[HRMS] ✓ Address: {address}", flush=True)
        
        # Step 7: Calculate Total Request Days
        print("[HRMS] Step 6/6: Calculating total request days...", flush=True)
        days_response = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveSetting/GetTotalRequestDays",
            params={
                "EmployeeLeaveRequestId": 0,
                "EmployeeId": employee_id,
                "LeaveTypeId": leave_type_id,
                "AppliedFromDate": from_date,
                "AppliedToDate": to_date
            },
            headers=headers,
            timeout=30.0,
            verify=False
        )
        print(f"[HRMS] Days Calculation Response (Status: {days_response.status_code}):", flush=True)
        print(f"[HRMS] DEBUG - Days Response Body:", flush=True)
        print(days_response.text[:500], flush=True)
        print("-" * 40, flush=True)
        
        calculated_days = total_days  # Use user-provided days for submission
        api_leave_count = 0  # Track API's calculation separately
        
        if days_response.status_code == 200:
            try:
                days_data = days_response.json()
                # API returns leaveCount as string - this is working days only
                leave_count_str = days_data.get("leaveCount") or days_data.get("value")
                if leave_count_str:
                    try:
                        api_leave_count = float(leave_count_str)
                    except (ValueError, TypeError):
                        pass
                
                # Check the list for warnings
                leave_list = days_data.get("list")
                if leave_list:
                    try:
                        import json as json_lib
                        list_data = json_lib.loads(leave_list) if isinstance(leave_list, str) else leave_list
                        has_already_applied = False
                        has_weekend = False
                        has_holiday = False
                        
                        for day_info in list_data:
                            remark = day_info.get("Remarks", "")
                            date = day_info.get("Date", "")
                            
                            if remark == "Already Applied":
                                has_already_applied = True
                                print(f"[HRMS] ⚠️  WARNING: Leave already applied for {date}", flush=True)
                            elif remark == "Weekend":
                                has_weekend = True
                                print(f"[HRMS] ℹ️  INFO: {date} is a weekend", flush=True)
                            elif remark == "Holiday" or "Holiday" in remark:
                                has_holiday = True
                                print(f"[HRMS] ℹ️  INFO: {date} is a holiday", flush=True)
                        
                        # If ALL days are already applied, abort
                        if has_already_applied and api_leave_count == 0 and not has_weekend and not has_holiday:
                            error_msg = "❌ Cannot apply leave: Leave has already been applied for the selected dates."
                            print(f"[HRMS] ❌ All days already applied, aborting", flush=True)
                            print("="*70 + "\n", flush=True)
                            return error_msg
                            
                    except Exception as e:
                        print(f"[HRMS] Warning: Could not parse leave list: {e}", flush=True)
                        
            except Exception as e:
                print(f"[HRMS] Warning: Could not parse days response: {e}", flush=True)
        
        print(f"[HRMS] ✓ API working days count: {api_leave_count}", flush=True)
        print(f"[HRMS] ✓ Using {calculated_days} day(s) for submission", flush=True)
        
        # Step 8: Generate LeaveDaysJson
        leave_days_json = _generate_leave_days_json(from_date, total_days)
        
        print("-" * 70, flush=True)
        print("[HRMS] Submitting leave request...", flush=True)
        
        # Step 9: Submit Leave Request
        # Build request body - for form data, convert None to empty string
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
            "AppliedTotalDays": calculated_days,
            "LeavePurpose": reason,
            "EmergencyPhoneNo": emergency_phone,
            "AddressDuringLeave": address,
            "Remarks": "",
            "LeaveDaysJson": json.dumps(leave_days_json),  # JSON string
            "FilePath": "",
            "Flag": "Submit",
            "EstimatedDeliveryDate": ""
        }
        
        print(f"[HRMS] Request payload prepared", flush=True)
        print(f"[HRMS] DEBUG - Full payload:", flush=True)
        print(json.dumps(request_body, indent=2), flush=True)
        
        leave_response = httpx.post(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/LeaveRequest/SaveEmployeeLeaveRequest3",
            data=request_body,  # Send as form data (x-www-form-urlencoded)
            headers={
                "Authorization": f"Bearer {token}"
            },
            timeout=30.0,
            verify=False
        )
        
        print("="*70, flush=True)
        print(f"[HRMS] FINAL SUBMISSION RESPONSE (Status: {leave_response.status_code})", flush=True)
        print(f"[HRMS] DEBUG - Full Response Body:", flush=True)
        print(leave_response.text, flush=True)
        print("="*70, flush=True)
        
        if leave_response.status_code == 200:
            result = leave_response.json() if leave_response.text else {}
            status = result.get("status", False)
            msg = result.get("msg", "")
            errors = result.get("errors", {})
            
            if status:
                success_msg = (
                            f"✅ Leave application submitted successfully!\n"
                            f"📅 Period: {from_date} to {to_date} ({calculated_days} days)\n"
                            f"📝 Reason: {reason}\n"
                            f"📱 Contact: {emergency_phone}\n"
                            f"🏠 Address: {address}"
                        )
                if msg:
                    success_msg += f"\n💬 Message: {msg}"
                print(f"[HRMS] ✅ SUCCESS", flush=True)
                print("="*70 + "\n", flush=True)
                return success_msg
        else:
            error_msg = f"❌ HTTP {leave_response.status_code}: {leave_response.text}"
            print(f"[HRMS] ❌ HTTP ERROR: {leave_response.status_code}", flush=True)
            print(f"[HRMS] Response body: {leave_response.text[:500]}", flush=True)  # First 500 chars
            print("="*70 + "\n", flush=True)
            return error_msg
            
    except Exception as e:
        error_msg = f"❌ Error during leave application: {str(e)}"
        print(f"[HRMS] ❌ EXCEPTION: {str(e)}", flush=True)
        print("="*70 + "\n", flush=True)
        return error_msg
