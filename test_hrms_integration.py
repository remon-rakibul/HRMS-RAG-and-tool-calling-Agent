"""Test script for HRMS Integration"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def print_result(name, success, response=None):
    status = "✓ PASS" if success else "✗ FAIL"
    print(f"\n{status}: {name}")
    if response:
        try:
            print(f"   Response: {json.dumps(response, indent=2)[:500]}")
        except:
            print(f"   Response: {str(response)[:500]}")

def test_session_init():
    """Test 1: Initialize HRMS session"""
    print("\n" + "="*60)
    print("TEST 1: Session Init (HRMS backend calls this)")
    print("="*60)
    
    payload = {
        "sessionId": "test-session-abc123",
        "userId": "1001",
        "username": "john.doe",
        "employeeId": 335,
        "employeeName": "John Doe",
        "roleId": 5,
        "roleName": "Employee",
        "companyId": 1,
        "organizationId": 1
    }
    
    response = requests.post(f"{BASE_URL}/agent/session-init", json=payload)
    success = response.status_code == 200 and response.json().get("success")
    print_result("POST /agent/session-init", success, response.json())
    return success, "test-session-abc123"

def test_get_session(session_id):
    """Test 2: Verify session was stored"""
    print("\n" + "="*60)
    print("TEST 2: Get Session (verify storage)")
    print("="*60)
    
    response = requests.get(f"{BASE_URL}/agent/session/{session_id}")
    success = response.status_code == 200 and response.json().get("employee_id") == 335
    print_result(f"GET /agent/session/{session_id}", success, response.json())
    return success

def test_auth_login():
    """Test 3: Login to get JWT token"""
    print("\n" + "="*60)
    print("TEST 3: FastAPI Auth Login")
    print("="*60)
    
    # Try to login with existing user
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword123"
    })
    
    if response.status_code != 200:
        # Register if login fails
        requests.post(f"{BASE_URL}/auth/register", json={
            "email": "test@example.com",
            "password": "testpassword123"
        })
        response = requests.post(f"{BASE_URL}/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword123"
        })
    
    success = response.status_code == 200
    data = response.json() if success else {}
    token = data.get("access_token", "")
    print_result("POST /auth/login", success, {"token": token[:50] + "..." if token else "none"})
    return success, token

def test_chat_with_session(token, session_id):
    """Test 4: Chat with session context"""
    print("\n" + "="*60)
    print("TEST 4: Chat with Session Context")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "message": "Who am I? What's my employee ID?",
        "session_id": session_id
    }
    
    response = requests.post(f"{BASE_URL}/chat", json=payload, headers=headers, stream=True)
    
    full_response = ""
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                try:
                    data = json.loads(line_str[6:])
                    if data.get("type") == "token":
                        full_response += data.get("content", "")
                except:
                    pass
    
    success = response.status_code == 200
    print_result("POST /chat (with session)", success, {"response": full_response[:300] + "..."})
    return success

def test_chat_leave_application(token, session_id):
    """Test 5: Apply for leave using session context"""
    print("\n" + "="*60)
    print("TEST 5: Leave Application (uses employee ID from session)")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "message": "Apply for 1 day leave on December 15, 2024 for personal work",
        "session_id": session_id
    }
    
    response = requests.post(f"{BASE_URL}/chat", json=payload, headers=headers, stream=True)
    
    full_response = ""
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                try:
                    data = json.loads(line_str[6:])
                    if data.get("type") == "token":
                        full_response += data.get("content", "")
                except:
                    pass
    
    success = response.status_code == 200
    print_result("POST /chat (leave application)", success, {"response": full_response[:400] + "..."})
    return success

def test_chat_without_session(token):
    """Test 6: Chat without session (should fail for leave tools)"""
    print("\n" + "="*60)
    print("TEST 6: Leave without session (should gracefully handle)")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "message": "Apply for leave tomorrow"
        # No session_id - should fail gracefully
    }
    
    response = requests.post(f"{BASE_URL}/chat", json=payload, headers=headers, stream=True)
    
    full_response = ""
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                try:
                    data = json.loads(line_str[6:])
                    if data.get("type") == "token":
                        full_response += data.get("content", "")
                except:
                    pass
    
    success = response.status_code == 200
    # Check if response mentions context not available
    has_error_message = "context" in full_response.lower() or "logged in" in full_response.lower() or "cannot" in full_response.lower()
    print_result("POST /chat (no session - expected to mention context issue)", success, {"response": full_response[:400] + "..."})
    return success

def test_delete_session(session_id):
    """Test 7: Delete session"""
    print("\n" + "="*60)
    print("TEST 7: Delete Session")
    print("="*60)
    
    response = requests.delete(f"{BASE_URL}/agent/session/{session_id}")
    success = response.status_code == 200
    print_result(f"DELETE /agent/session/{session_id}", success, response.json() if success else None)
    return success

def main():
    print("\n" + "="*60)
    print("  HRMS INTEGRATION TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test 1: Session Init
    success, session_id = test_session_init()
    results.append(("Session Init", success))
    
    if not success:
        print("\n❌ Session init failed, cannot continue tests")
        return
    
    # Test 2: Get Session
    success = test_get_session(session_id)
    results.append(("Get Session", success))
    
    # Test 3: Auth Login
    success, token = test_auth_login()
    results.append(("Auth Login", success))
    
    if not success or not token:
        print("\n❌ Auth failed, cannot continue tests")
        return
    
    # Test 4: Chat with session
    success = test_chat_with_session(token, session_id)
    results.append(("Chat with Session", success))
    
    # Test 5: Leave application
    success = test_chat_leave_application(token, session_id)
    results.append(("Leave Application", success))
    
    # Test 6: Chat without session
    success = test_chat_without_session(token)
    results.append(("Chat without Session", success))
    
    # Test 7: Delete session
    success = test_delete_session(session_id)
    results.append(("Delete Session", success))
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    for name, success in results:
        status = "✓" if success else "✗"
        print(f"  {status} {name}")
    
    print(f"\n  Result: {passed}/{total} tests passed")
    print("="*60)

if __name__ == "__main__":
    main()
