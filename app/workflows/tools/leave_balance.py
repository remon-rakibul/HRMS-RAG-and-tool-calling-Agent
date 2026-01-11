"""HRMS Leave Balance Tool.

This tool allows users to check their leave balance from the HRMS API.
It handles authentication and retrieves the current leave balance for the logged-in employee.
"""

from typing import Annotated, Optional
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


@tool_registry.register
def get_leave_balance(
    employee_id: Annotated[Optional[int], "Employee ID (optional, defaults to logged-in user)"] = None
) -> str:
    """Get the current user's leave balance from the HRMS system.
    
    Use this when the user asks about:
    - "How many leave days do I have left?"
    - "What's my leave balance?"
    - "Check my remaining vacation days"
    - "Show me my leave balance"
    - "How many leaves do I have?"
    
    This tool retrieves the leave balance information from the HRMS API for the logged-in employee.
    """
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
    print("[HRMS] LEAVE BALANCE REQUEST", flush=True)
    print("="*70, flush=True)
    print(f"[HRMS] Employee ID: {employee_id}", flush=True)
    print("-" * 70, flush=True)
    
    # Step 1: Authenticate
    token = _get_hrms_token()
    if not token:
        return "❌ Failed to authenticate with HRMS system. Please try again later."
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Step 2: Get Leave Balance
        print("[HRMS] Fetching leave balance...", flush=True)
        balance_response = httpx.get(
            f"{HRMS_BASE_URL}/api/HRMS/Leave/EmployeeLeaveBalance/GetLeaveBalance",
            params={"employeeId": employee_id},
            headers=headers,
            timeout=30.0,
            verify=False
        )
        
        print(f"[HRMS] Response Status: {balance_response.status_code}", flush=True)
        print(f"[HRMS] DEBUG - Full Response Body:", flush=True)
        print(balance_response.text, flush=True)
        print("-" * 70, flush=True)
        
        if balance_response.status_code == 200:
            try:
                balance_data = balance_response.json()
                
                print(f"[HRMS] DEBUG - Parsed JSON Response:", flush=True)
                print(json.dumps(balance_data, indent=2, default=str), flush=True)
                print("-" * 70, flush=True)
                
                # Return the full JSON response as a formatted string
                json_response = json.dumps(balance_data, indent=2, default=str)
                
                print("[HRMS] ✓ Leave balance retrieved successfully", flush=True)
                print("="*70 + "\n", flush=True)
                return json_response
                    
            except Exception as e:
                print(f"[HRMS] ❌ Error parsing response: {str(e)}", flush=True)
                print(f"[HRMS] Response text: {balance_response.text[:500]}", flush=True)
                return f"❌ Error retrieving leave balance: Failed to parse response. Status: {balance_response.status_code}"
        else:
            error_msg = f"❌ Failed to retrieve leave balance. HTTP {balance_response.status_code}: {balance_response.text[:200]}"
            print(f"[HRMS] ❌ {error_msg}", flush=True)
            print("="*70 + "\n", flush=True)
            return error_msg
            
    except Exception as e:
        error_msg = f"❌ Error during leave balance retrieval: {str(e)}"
        print(f"[HRMS] ❌ EXCEPTION: {str(e)}", flush=True)
        print("="*70 + "\n", flush=True)
        return error_msg

