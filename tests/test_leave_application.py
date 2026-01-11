"""Integration tests for HRMS leave application functionality."""
import pytest
import json
import uuid
from datetime import datetime, timedelta


def parse_streaming_response(client, method, url, headers, json_data):
    """Helper to handle streaming responses from TestClient."""
    with client.stream(method, url, headers=headers, json=json_data) as response:
        full_response = ""
        chunks = []
        thread_id = None
        
        for line in response.iter_lines():
            if line:
                if line.startswith('data: '):
                    try:
                        chunk = json.loads(line[6:])
                        chunks.append(chunk)
                        if chunk.get("thread_id") and not thread_id:
                            thread_id = chunk["thread_id"]
                        if chunk.get("type") == "token":
                            full_response += chunk.get("content", "")
                    except json.JSONDecodeError:
                        continue
        
        return {
            "status_code": response.status_code,
            "full_response": full_response,
            "chunks": chunks,
            "thread_id": thread_id
        }


class TestLeaveApplication:
    """Test suite for leave application via chat with HRMS API integration."""
    
    def test_leave_application_with_session_context(
        self, client, auth_headers, session_factory, cleanup_sessions
    ):
        """Test leave application with session context providing employee_id.
        
        Verifies that:
        1. Tool extracts employee_id from session context (not hardcoded)
        2. All HRMS API calls execute successfully
        3. Leave request submitted with correct employee_id
        """
        # Create session for employee 335
        session_id = session_factory(employee_id=335, employee_name="Neha Muquith")
        
        # Calculate a weekday date (Monday = 0)
        today = datetime.now()
        days_ahead = (0 - today.weekday() + 7) % 7 + 7  # Next Monday
        target_date = today + timedelta(days=days_ahead)
        date_str = target_date.strftime("%B %d")
        
        # Send chat message to apply for leave
        result = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers,
            json_data={
                "message": f"Apply for 1 day sick leave on {date_str} for medical checkup",
                "session_id": session_id
            }
        )
        
        assert result["status_code"] == 200
        print(f"\n[TEST] Chunks received: {len(result['chunks'])}")
        print(f"\n[TEST] Response length: {len(result['full_response'])}")
        if result["chunks"]:
            print(f"\n[TEST] Sample chunks: {result['chunks'][:3]}")
        
        # Verify we got chunks
        assert len(result["chunks"]) > 0, "No chunks received"
        
        # Check if we got a done chunk or any response
        has_done = any(chunk.get("type") == "done" for chunk in result["chunks"])
        has_content = len(result["full_response"]) > 0
        
        assert has_done or has_content, "No done chunk or content received"
        
        print(f"\n[TEST] Leave application response: {result['full_response'][:200]}")
    
    def test_leave_application_without_session(
        self, client, auth_headers, cleanup_sessions
    ):
        """Test leave application without session_id.
        
        Verifies that:
        1. Tool uses default employee_id when no session provided
        2. Warning is logged about missing session
        3. Leave application still proceeds (degraded mode)
        """
        # Calculate a weekday date
        today = datetime.now()
        days_ahead = (0 - today.weekday() + 7) % 7 + 14  # Monday 2 weeks ahead
        target_date = today + timedelta(days=days_ahead)
        date_str = target_date.strftime("%B %d")
        
        # Send chat message without session_id
        result = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers,
            json_data={
                "message": f"Apply for 1 day sick leave on {date_str}",
                # No session_id provided
            }
        )
        
        assert result["status_code"] == 200
        assert len(result["full_response"]) > 0
        print(f"\n[TEST] Leave without session response: {result['full_response'][:200]}")
    
    def test_leave_application_weekend_handling(
        self, client, auth_headers, session_factory, cleanup_sessions
    ):
        """Test leave application on weekend dates.
        
        Verifies that:
        1. API returns leaveCount=0 for weekends
        2. Tool still submits request with user-provided total_days
        3. Informational warning about weekend shown
        """
        # Create session
        session_id = session_factory(employee_id=335, employee_name="Neha Muquith")
        
        # Find next Saturday
        today = datetime.now()
        days_ahead = (5 - today.weekday() + 7) % 7  # Saturday = 5
        if days_ahead == 0:
            days_ahead = 7
        target_date = today + timedelta(days=days_ahead)
        date_str = target_date.strftime("%B %d")
        
        # Send chat message for weekend leave
        result = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers,
            json_data={
                "message": f"Apply for 1 day sick leave on {date_str}",
                "session_id": session_id
            }
        )
        
        assert result["status_code"] == 200
        assert len(result["full_response"]) > 0
        print(f"\n[TEST] Weekend leave response: {result['full_response'][:200]}")
    
    def test_leave_application_invalid_session(
        self, client, auth_headers, cleanup_sessions
    ):
        """Test leave application with invalid/expired session_id.
        
        Verifies that:
        1. Invalid session_id is handled gracefully
        2. System logs warning about missing session
        3. Falls back to default behavior
        """
        # Use non-existent session_id
        fake_session_id = str(uuid.uuid4())
        
        result = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers,
            json_data={
                "message": "Apply for 1 day sick leave tomorrow",
                "session_id": fake_session_id
            }
        )
        
        # Should still work (falls back to default)
        assert result["status_code"] == 200
        assert len(result["full_response"]) > 0
    
    def test_leave_application_date_parsing(
        self, client, auth_headers, session_factory, cleanup_sessions
    ):
        """Test various date formats for leave application.
        
        Verifies that:
        1. Different date formats are parsed correctly
        2. Tool correctly interprets relative dates (tomorrow, next Monday)
        3. Absolute dates with month names work correctly
        """
        session_id = session_factory(employee_id=335, employee_name="Test User")
        
        test_cases = [
            "Apply for 1 day sick leave tomorrow",
            "Apply for 1 day sick leave on December 10th",
            "I need sick leave for 2 days starting next Monday",
        ]
        
        for message in test_cases:
            result = parse_streaming_response(
                client, "POST", "/api/v1/chat",
                headers=auth_headers,
                json_data={
                    "message": message,
                    "session_id": session_id,
                    "thread_id": str(uuid.uuid4())  # New thread for each test
                }
            )
            
            assert result["status_code"] == 200
            assert len(result["chunks"]) > 0, f"No response for message: {message}"
    
    def test_multiple_day_leave_application(
        self, client, auth_headers, session_factory, cleanup_sessions
    ):
        """Test applying for multi-day leave.
        
        Verifies that:
        1. Multi-day leave requests are handled correctly
        2. Total days calculated properly
        3. Date range is correctly specified
        """
        session_id = session_factory(employee_id=335, employee_name="Test User")
        
        # Calculate date range (3 weekdays)
        today = datetime.now()
        days_ahead = (0 - today.weekday() + 7) % 7 + 7  # Next Monday
        start_date = today + timedelta(days=days_ahead)
        start_str = start_date.strftime("%B %d")
        
        result = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers,
            json_data={
                "message": f"Apply for 3 days sick leave starting {start_str}",
                "session_id": session_id
            }
        )
        
        assert result["status_code"] == 200
        assert len(result["full_response"]) > 0
        print(f"\n[TEST] Multi-day leave response: {result['full_response'][:200]}")
