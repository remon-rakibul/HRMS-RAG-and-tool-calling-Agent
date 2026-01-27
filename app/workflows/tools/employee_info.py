"""HRMS Employee Information Tool.

This tool allows users to retrieve their personal employee information from the HRMS API.
It handles authentication and retrieves employee details such as name, department, designation, etc.
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
def get_employee_info(
    employee_id: Annotated[Optional[int], "Employee ID (optional, defaults to logged-in user)"] = None
) -> str:
    """Get the current user's employee personal information from the HRMS system.
    
    Use this when the user asks about:
    - "Who am I?"
    - "Where do I work?"
    - "What is my employee information?"
    - "Tell me about myself"
    - "What department am I in?"
    - "What is my designation?"
    - "What is my job title?"
    - "What is my employee ID?"
    - "Show me my profile"
    - "What are my employee details?"
    - "Who is my manager?"
    - "What branch do I work at?"
    
    This tool retrieves comprehensive employee personal information from the HRMS API 
    for the logged-in employee, including name, department, designation, branch, 
    manager information, and other personal details.
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
    print("[HRMS] EMPLOYEE INFORMATION REQUEST", flush=True)
    print("="*70, flush=True)
    print(f"[HRMS] Employee ID: {employee_id}", flush=True)
    print("-" * 70, flush=True)
    
    # Step 1: Authenticate
    token = _get_hrms_token()
    if not token:
        return "❌ Failed to authenticate with HRMS system. Please try again later."
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Step 2: Get Employee Personal Information
        print("[HRMS] Fetching employee information...", flush=True)
        info_response = httpx.get(
            f"{HRMS_BASE_URL}/api/hrms/Employee/Info/GetEmployeePersonalInfoById",
            params={"employeeId": employee_id},
            headers=headers,
            timeout=30.0,
            verify=False
        )
        
        print(f"[HRMS] Response Status: {info_response.status_code}", flush=True)
        print(f"[HRMS] DEBUG - Full Response Body:", flush=True)
        print(info_response.text, flush=True)
        print("-" * 70, flush=True)
        
        if info_response.status_code == 200:
            try:
                employee_data = info_response.json()
                
                print(f"[HRMS] DEBUG - Parsed JSON Response:", flush=True)
                print(json.dumps(employee_data, indent=2, default=str), flush=True)
                print("-" * 70, flush=True)
                
                # Return the full JSON response as a formatted string
                json_response = json.dumps(employee_data, indent=2, default=str)
                
                print("[HRMS] ✓ Employee information retrieved successfully", flush=True)
                print("="*70 + "\n", flush=True)
                return json_response
                    
            except Exception as e:
                print(f"[HRMS] ❌ Error parsing response: {str(e)}", flush=True)
                print(f"[HRMS] Response text: {info_response.text[:500]}", flush=True)
                return f"❌ Error retrieving employee information: Failed to parse response. Status: {info_response.status_code}"
        else:
            error_msg = f"❌ Failed to retrieve employee information. HTTP {info_response.status_code}: {info_response.text[:200]}"
            print(f"[HRMS] ❌ {error_msg}", flush=True)
            print("="*70 + "\n", flush=True)
            return error_msg
            
    except Exception as e:
        error_msg = f"❌ Error during employee information retrieval: {str(e)}"
        print(f"[HRMS] ❌ EXCEPTION: {str(e)}", flush=True)
        print("="*70 + "\n", flush=True)
        return error_msg
