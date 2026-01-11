"""HRMS Manual Attendance Application Tool.

This tool allows users to apply for manual attendance through the HRMS API.
It handles the complete manual attendance application workflow:
1. Authenticate with admin credentials
2. Format attendance date and times
3. Submit manual attendance request
"""

from typing import Annotated, Optional
from datetime import datetime
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


def _format_attendance_date(date_str: str) -> str:
    """Convert date string to ISO datetime format for attendance (YYYY-MM-DDTHH:mm:ss.000Z)."""
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
            # Return in ISO format with time (00:00:00.000Z)
            return dt.strftime("%Y-%m-%dT00:00:00.000Z")
        except ValueError:
            continue
    
    formats_without_year = ["%B %d", "%b %d", "%m-%d", "%m/%d"]
    
    for fmt in formats_without_year:
        try:
            dt = datetime.strptime(date_str, fmt)
            dt = dt.replace(year=current_year)
            return dt.strftime("%Y-%m-%dT00:00:00.000Z")
        except ValueError:
            continue
    
    # If parsing fails, try to use the date string directly if it's already in ISO format
    if "T" in date_str or len(date_str) == 10:
        try:
            # Try to parse as YYYY-MM-DD
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return dt.strftime("%Y-%m-%dT00:00:00.000Z")
        except ValueError:
            pass
    
    return date_str


def _format_time(time_str: str) -> str:
    """Format time string to HH:MM format (e.g., '09:00', '9:00 AM' -> '09:00')."""
    time_str = time_str.strip()
    
    # If already in HH:MM format, return as is
    if len(time_str) == 5 and time_str[2] == ":":
        try:
            hours, minutes = time_str.split(":")
            hours_int = int(hours)
            minutes_int = int(minutes)
            if 0 <= hours_int < 24 and 0 <= minutes_int < 60:
                return f"{hours_int:02d}:{minutes_int:02d}"
        except ValueError:
            pass
    
    # Try to parse various time formats
    time_formats = [
        "%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p",
        "%I:%M%p", "%I:%M:%S%p", "%H:%M:%S.%f"
    ]
    
    for fmt in time_formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.strftime("%H:%M")
        except ValueError:
            continue
    
    # If all parsing fails, try to extract just numbers
    import re
    numbers = re.findall(r'\d+', time_str)
    if len(numbers) >= 2:
        try:
            hours = int(numbers[0])
            minutes = int(numbers[1])
            if 0 <= hours < 24 and 0 <= minutes < 60:
                # Handle 12-hour format
                if "PM" in time_str.upper() and hours != 12:
                    hours += 12
                elif "AM" in time_str.upper() and hours == 12:
                    hours = 0
                return f"{hours:02d}:{minutes:02d}"
        except ValueError:
            pass
    
    # Return original if we can't parse
    return time_str


@tool_registry.register
def apply_for_manual_attendance(
    attendance_date: Annotated[str, "Attendance date in YYYY-MM-DD format (e.g., '2026-01-04')"],
    reason: Annotated[str, "Reason for manual attendance."],
    in_time: Annotated[Optional[str], "In-time in HH:MM format (e.g., '09:00'). Provide if user wants to mark in-time"] = None,
    out_time: Annotated[Optional[str], "Out-time in HH:MM format (e.g., '18:00'). Provide if user wants to mark out-time"] = None,
    time_request_for: Annotated[Optional[str], "Time request type: 'Both', 'In-Time', or 'Out-Time'. Auto-detected from in_time/out_time if not provided"] = None,
    employee_id: Annotated[Optional[int], "Employee ID (optional, defaults to logged-in user)"] = None
) -> str:
    """Apply for manual attendance in the HRMS system. Use this when the user wants to request manual attendance, mark attendance manually, or needs to record attendance for a specific date.
    
    This tool handles the complete manual attendance application workflow.
    
    IMPORTANT: 
    - You MUST ask the user for a reason if they don't provide one. The reason is required.
    - The tool will automatically determine timeRequestFor based on what times are provided (in_time, out_time, or both).
    - If user provides only in_time -> timeRequestFor = "In-Time"
    - If user provides only out_time -> timeRequestFor = "Out-Time"
    - If user provides both -> timeRequestFor = "Both"
    
    Examples:
    - "Apply for manual attendance for January 4th, 2026, in-time 9:00 AM, out-time 6:00 PM, reason: could not reach office in time"
    - "Request manual attendance for today, in-time only at 10:00 AM, reason: late arrival"
    - "Mark manual attendance for tomorrow, out-time only at 5:00 PM, reason: early departure"
    """
    # Validate reason is provided
    if not reason or not reason.strip():
        return "❌ Reason is required for manual attendance application. Please provide a reason (e.g., 'could not reach office in time', 'late arrival', etc.)."
    
    # Auto-detect timeRequestFor from provided times if not explicitly provided
    if time_request_for:
        # Normalize time_request_for if provided
        time_request_for = time_request_for.strip()
        if time_request_for.lower() in ["both", "both times", "all"]:
            time_request_for = "Both"
        elif time_request_for.lower() in ["in-time", "in time", "in", "entry"]:
            time_request_for = "In-Time"
        elif time_request_for.lower() in ["out-time", "out time", "out", "exit"]:
            time_request_for = "Out-Time"
        else:
            # If not recognized, auto-detect from times
            time_request_for = None
    
    # Auto-detect timeRequestFor based on provided times
    if not time_request_for:
        if in_time and out_time:
            time_request_for = "Both"
        elif in_time:
            time_request_for = "In-Time"
        elif out_time:
            time_request_for = "Out-Time"
        else:
            return "❌ At least one time (in-time or out-time) must be provided for manual attendance application."
    
    # Validate that times match timeRequestFor
    if time_request_for in ["Both", "In-Time"]:
        if not in_time:
            return f"❌ In-time is required when timeRequestFor is '{time_request_for}'. Please provide the in-time."
    
    if time_request_for in ["Both", "Out-Time"]:
        if not out_time:
            return f"❌ Out-time is required when timeRequestFor is '{time_request_for}'. Please provide the out-time."
    
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
    
    print("\n" + "="*70, flush=True)
    print("[HRMS] MANUAL ATTENDANCE APPLICATION PROCESS STARTED", flush=True)
    print("="*70, flush=True)
    
    # Format attendance date
    formatted_date = _format_attendance_date(attendance_date)
    
    # Format times only if provided
    formatted_in_time = _format_time(in_time) if in_time else None
    formatted_out_time = _format_time(out_time) if out_time else None
    
    print(f"[HRMS] Employee ID: {employee_id}", flush=True)
    print(f"[HRMS] Attendance Date: {attendance_date} -> {formatted_date}", flush=True)
    print(f"[HRMS] Time Request For: {time_request_for}", flush=True)
    if formatted_in_time:
        print(f"[HRMS] In-Time: {formatted_in_time}", flush=True)
    if formatted_out_time:
        print(f"[HRMS] Out-Time: {formatted_out_time}", flush=True)
    print(f"[HRMS] Reason: {reason}", flush=True)
    print("-" * 70, flush=True)
    
    # Step 1: Authenticate
    token = _get_hrms_token()
    if not token:
        return "❌ Failed to authenticate with HRMS system."
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Step 2: Prepare request body
        # Only include inTime and outTime if they are provided
        request_body = {
            "manualAttendanceId": 0,
            "manualAttendanceCode": "",
            "employeeId": employee_id,
            "departmentId": 0,
            "sectionId": 0,
            "unitId": 0,
            "attendanceDate": formatted_date,
            "timeRequestFor": time_request_for,
            "stateStatus": "",
            "reason": reason,
            "remarks": "",
            "attendanceType": "Official Instruction"
        }
        
        # Conditionally add inTime and outTime based on what's provided
        # Send null instead of empty string when not provided
        if formatted_in_time:
            request_body["inTime"] = formatted_in_time
        else:
            request_body["inTime"] = None
        
        if formatted_out_time:
            request_body["outTime"] = formatted_out_time
        else:
            request_body["outTime"] = None
        
        print(f"[HRMS] Submitting manual attendance request...", flush=True)
        print(f"[HRMS] DEBUG - Full payload:", flush=True)
        print(json.dumps(request_body, indent=2), flush=True)
        print("-" * 70, flush=True)
        
        # Step 3: Submit Manual Attendance Request
        attendance_response = httpx.post(
            f"{HRMS_BASE_URL}/api/hrms/Attendance/ManualAttendance/SaveManualAttendance",
            json=request_body,
            headers=headers,
            timeout=30.0,
            verify=False
        )
        
        print("="*70, flush=True)
        print(f"[HRMS] FINAL SUBMISSION RESPONSE (Status: {attendance_response.status_code})", flush=True)
        print(f"[HRMS] DEBUG - Full Response Body:", flush=True)
        print(attendance_response.text, flush=True)
        print("="*70, flush=True)
        
        if attendance_response.status_code == 200:
            try:
                result = attendance_response.json() if attendance_response.text else {}
                status = result.get("status", False)
                msg = result.get("msg", "")
                errors = result.get("errors", {})
                
                if status:
                    success_msg = (
                        f"✅ Manual attendance application submitted successfully!\n"
                        f"📅 Date: {attendance_date}\n"
                        f"⏰ Time Request: {time_request_for}\n"
                    )
                    if formatted_in_time:
                        success_msg += f"🕐 In-Time: {formatted_in_time}\n"
                    if formatted_out_time:
                        success_msg += f"🕐 Out-Time: {formatted_out_time}\n"
                    success_msg += f"📝 Reason: {reason}"
                    if msg:
                        success_msg += f"\n💬 Message: {msg}"
                    print(f"[HRMS] ✅ SUCCESS", flush=True)
                    print("="*70 + "\n", flush=True)
                    return success_msg
                else:
                    error_msg = f"❌ Manual attendance application failed."
                    if msg:
                        error_msg += f"\n💬 Message: {msg}"
                    if errors:
                        error_msg += f"\n❌ Errors: {json.dumps(errors, indent=2)}"
                    print(f"[HRMS] ❌ FAILED: {msg}", flush=True)
                    print("="*70 + "\n", flush=True)
                    return error_msg
            except Exception as e:
                # Response might not be JSON
                if attendance_response.text:
                    if "success" in attendance_response.text.lower() or "submitted" in attendance_response.text.lower():
                        success_msg = (
                            f"✅ Manual attendance application submitted successfully!\n"
                            f"📅 Date: {attendance_date}\n"
                            f"⏰ Time Request: {time_request_for}\n"
                        )
                        if formatted_in_time:
                            success_msg += f"🕐 In-Time: {formatted_in_time}\n"
                        if formatted_out_time:
                            success_msg += f"🕐 Out-Time: {formatted_out_time}\n"
                        success_msg += f"📝 Reason: {reason}"
                        print(f"[HRMS] ✅ SUCCESS (non-JSON response)", flush=True)
                        print("="*70 + "\n", flush=True)
                        return success_msg
                
                error_msg = f"❌ Error parsing response: {str(e)}\nResponse: {attendance_response.text[:500]}"
                print(f"[HRMS] ❌ PARSE ERROR: {str(e)}", flush=True)
                print("="*70 + "\n", flush=True)
                return error_msg
        else:
            error_msg = f"❌ HTTP {attendance_response.status_code}: {attendance_response.text[:500]}"
            print(f"[HRMS] ❌ HTTP ERROR: {attendance_response.status_code}", flush=True)
            print(f"[HRMS] Response body: {attendance_response.text[:500]}", flush=True)
            print("="*70 + "\n", flush=True)
            return error_msg
            
    except Exception as e:
        error_msg = f"❌ Error during manual attendance application: {str(e)}"
        print(f"[HRMS] ❌ EXCEPTION: {str(e)}", flush=True)
        print("="*70 + "\n", flush=True)
        return error_msg