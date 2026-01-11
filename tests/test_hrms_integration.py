"""Integration tests for HRMS session management and employee context."""
import pytest
import time
import uuid
from app.models.agent_session import get_session
from app.core.database import get_db


class TestSessionManagement:
    """Test suite for HRMS session initialization and context retrieval."""
    
    def test_session_init_and_context_retrieval(self, client, auth_headers, cleanup_sessions, db_session):
        """Test session initialization and context retrieval.
        
        Verifies that:
        1. Session can be initialized with employee data
        2. Session is stored in database
        3. Retrieved session context matches initialization data
        """
        # Initialize session with employee data
        session_id = str(uuid.uuid4())
        employee_id = 335
        employee_name = "Neha Muquith"
        
        response = client.post(
            "/api/v1/agent/session-init",
            json={
                "sessionId": session_id,
                "employeeId": employee_id,
                "employeeName": employee_name
            },
            headers=auth_headers
        )
        
        # Verify initialization response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["sessionId"] == session_id
        assert data["message"] == "Session initialized"
        
        # Verify session is stored in database
        context = get_session(db=db_session, session_id=session_id)
        assert context is not None
        assert context.session_id == session_id
        assert context.employee_id == employee_id
        assert context.employee_name == employee_name
        
        # Verify session can be retrieved via API
        get_response = client.get(f"/api/v1/agent/session/{session_id}", headers=auth_headers)
        assert get_response.status_code == 200
        session_data = get_response.json()
        assert session_data["session_id"] == session_id
        assert session_data["employee_id"] == employee_id
        assert session_data["employee_name"] == employee_name
    
    def test_session_expiration(self, client, auth_headers, cleanup_sessions, db_session):
        """Test that sessions expire after TTL.
        
        Verifies that:
        1. Session can be created with expiration
        2. Session expires after configured TTL
        3. Expired session returns None/404
        """
        from app.models.agent_session import create_session
        from datetime import datetime, timezone, timedelta
        
        # Create a session with short TTL for testing (~1 second)
        session_id = str(uuid.uuid4())
        session = create_session(
            db=db_session,
            session_id=session_id,
            employee_id=335,
            employee_name="Test User",
            ttl_hours=0.0003  # ~1 second
        )
        
        # Verify session exists
        retrieved = get_session(db=db_session, session_id=session_id)
        assert retrieved is not None
        assert retrieved.employee_id == 335
        
        # Wait for expiration (1.5 seconds to be safe)
        time.sleep(1.5)
        
        # Verify session has expired
        expired = get_session(db=db_session, session_id=session_id)
        assert expired is None
    
    def test_multiple_sessions(self, client, auth_headers, cleanup_sessions, db_session):
        """Test multiple concurrent sessions for different employees.
        
        Verifies that:
        1. Multiple sessions can be initialized independently
        2. Each session maintains its own employee context
        3. Sessions don't interfere with each other
        """
        # Initialize 3 different sessions
        sessions = [
            {"id": str(uuid.uuid4()), "employee_id": 335, "name": "Neha Muquith"},
            {"id": str(uuid.uuid4()), "employee_id": 336, "name": "John Doe"},
            {"id": str(uuid.uuid4()), "employee_id": 337, "name": "Jane Smith"},
        ]
        
        # Create all sessions
        for session in sessions:
            response = client.post(
                "/api/v1/agent/session-init",
                json={
                    "sessionId": session["id"],
                    "employeeId": session["employee_id"],
                    "employeeName": session["name"]
                },
                headers=auth_headers
            )
            assert response.status_code == 200
            assert response.json()["success"] is True
        
        # Verify all sessions stored independently in database
        for session in sessions:
            context = get_session(db=db_session, session_id=session["id"])
            assert context is not None
            assert context.session_id == session["id"]
            assert context.employee_id == session["employee_id"]
            assert context.employee_name == session["name"]
        
        # Verify correct employee_id retrieved for each session
        for session in sessions:
            get_response = client.get(f"/api/v1/agent/session/{session['id']}", headers=auth_headers)
            assert get_response.status_code == 200
            data = get_response.json()
            assert data["employee_id"] == session["employee_id"]
            assert data["employee_name"] == session["name"]
    
    def test_session_deletion(self, client, auth_headers, cleanup_sessions, db_session):
        """Test session deletion/invalidation.
        
        Verifies that:
        1. Session can be deleted via API
        2. Deleted session is removed from store
        3. Attempting to retrieve deleted session returns 404
        """
        # Create session
        session_id = str(uuid.uuid4())
        response = client.post(
            "/api/v1/agent/session-init",
            json={
                "sessionId": session_id,
                "employeeId": 335,
                "employeeName": "Test User"
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify session exists
        get_response = client.get(f"/api/v1/agent/session/{session_id}", headers=auth_headers)
        assert get_response.status_code == 200
        
        # Delete session
        delete_response = client.delete(f"/api/v1/agent/session/{session_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        assert delete_response.json()["success"] is True
        
        # Verify session no longer exists
        get_after_delete = client.get(f"/api/v1/agent/session/{session_id}", headers=auth_headers)
        assert get_after_delete.status_code == 404
        
        # Verify it's removed from database
        context = get_session(db=db_session, session_id=session_id)
        assert context is None
    
    def test_session_not_found(self, client, auth_headers):
        """Test retrieving non-existent session returns 404."""
        non_existent_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/agent/session/{non_existent_id}", headers=auth_headers)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

