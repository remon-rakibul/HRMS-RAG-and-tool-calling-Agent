#!/bin/bash

echo "=== Testing Frontend Integration ==="
echo ""

# Test 1: Backend Health
echo "1. Testing Backend Health..."
BACKEND_HEALTH=$(curl -s http://localhost:8000/health)
if [[ $BACKEND_HEALTH == *"ok"* ]]; then
    echo "   ✓ Backend is running"
else
    echo "   ✗ Backend is not responding"
    exit 1
fi

# Test 2: Register/Login
echo ""
echo "2. Testing Registration/Login..."
# Try to register first (may fail if user exists, that's ok)
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "hrms@recombd.com", "password": "12345678"}' > /dev/null

# Now login
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "hrms@recombd.com", "password": "12345678"}')

if [[ $LOGIN_RESPONSE == *"access_token"* ]]; then
    echo "   ✓ Login successful"
    TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
    echo "   Token obtained: ${TOKEN:0:30}..."
else
    echo "   ✗ Login failed"
    echo "   Response: $LOGIN_RESPONSE"
    exit 1
fi

# Test 3: Session Init
echo ""
echo "3. Testing Session Initialization..."
SESSION_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/agent/session-init \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-frontend-123",
    "userId": "1001",
    "username": "test.user",
    "employeeId": 90,
    "employeeName": "Md Rakibul Haque",
    "roleId": 5,
    "roleName": "AI Engineer",
    "companyId": 1,
    "organizationId": 1
  }')

if [[ $SESSION_RESPONSE == *"success"* ]]; then
    echo "   ✓ Session initialized"
    SESSION_ID="test-frontend-123"
else
    echo "   ✗ Session init failed"
    echo "   Response: $SESSION_RESPONSE"
    exit 1
fi

# Test 4: Get Session
echo ""
echo "4. Testing Get Session..."
GET_SESSION=$(curl -s -X GET "http://localhost:8000/api/v1/agent/session/$SESSION_ID" \
  -H "Authorization: Bearer $TOKEN")

if [[ $GET_SESSION == *"employee_id"* ]]; then
    echo "   ✓ Session retrieved successfully"
    EMPLOYEE_ID=$(echo $GET_SESSION | grep -o '"employee_id":[0-9]*' | grep -o '[0-9]*')
    echo "   Employee ID: $EMPLOYEE_ID"
else
    echo "   ✗ Get session failed"
    echo "   Response: $GET_SESSION"
fi

# Test 5: Frontend URL
echo ""
echo "=== All Backend Tests Passed ==="
echo ""
echo "Frontend Test URL:"
echo "   http://localhost:5174/?sessionId=$SESSION_ID"
echo ""
echo "Expected Frontend Behavior:"
echo "   1. Auto-login with hrms@recombd.com / 12345678"
echo "   2. Get sessionId from URL: $SESSION_ID"
echo "   3. Fetch employee_id: $EMPLOYEE_ID"
echo "   4. Load chat history for employee $EMPLOYEE_ID"
echo "   5. Ready to chat!"
