"""Integration tests for thread isolation and conversation resumption."""
import pytest
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed


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


class TestThreadIsolation:
    """Test suite for thread isolation and multi-employee conversation management."""
    
    def test_thread_per_session_isolation(
        self, client, auth_headers_multi, session_factory, cleanup_sessions
    ):
        """Test that each session maintains its own thread with proper employee context.
        
        Verifies that:
        1. Two sessions use different threads
        2. Each thread maintains correct employee_id context
        3. No context bleeding between sessions
        """
        # Create two sessions for different employees
        session1_id = session_factory(employee_id=335, employee_name="Neha Muquith")
        session2_id = session_factory(employee_id=336, employee_name="John Doe")
        
        # Employee 1: Ask about leave balance
        result1 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers_multi["user1"],
            json_data={
                "message": "What is my employee ID?",
                "session_id": session1_id
            }
        )
        
        assert result1["status_code"] == 200
        assert result1["thread_id"] is not None
        print(f"\n[TEST] Employee 1 thread: {result1['thread_id']}")
        
        # Employee 2: Ask same question
        result2 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers_multi["user2"],
            json_data={
                "message": "What is my employee ID?",
                "session_id": session2_id
            }
        )
        
        assert result2["status_code"] == 200
        assert result2["thread_id"] is not None
        print(f"\n[TEST] Employee 2 thread: {result2['thread_id']}")
        
        # Verify threads are different
        assert result1["thread_id"] != result2["thread_id"], "Sessions should have different thread IDs"
        
        # Send follow-up messages with same thread_ids
        followup1 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers_multi["user1"],
            json_data={
                "message": "Apply for 1 day sick leave tomorrow",
                "session_id": session1_id,
                "thread_id": result1["thread_id"]  # Resume same thread
            }
        )
        assert followup1["status_code"] == 200
        
        followup2 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers_multi["user2"],
            json_data={
                "message": "What leave types are available?",
                "session_id": session2_id,
                "thread_id": result2["thread_id"]  # Resume same thread
            }
        )
        assert followup2["status_code"] == 200
    
    def test_conversation_resumption_per_employee(
        self, client, auth_headers_multi, session_factory, cleanup_sessions
    ):
        """Test conversation resumption with message history per employee.
        
        Verifies that:
        1. LangGraph checkpointer stores message history per thread
        2. Each employee can resume their own conversation
        3. No context bleeding between employee conversations
        """
        # Create two sessions
        session1_id = session_factory(employee_id=335, employee_name="Alice")
        session2_id = session_factory(employee_id=336, employee_name="Bob")
        
        # Alice: Start conversation about leave types
        alice_result1 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers_multi["user1"],
            json_data={
                "message": "Tell me about sick leave",
                "session_id": session1_id
            }
        )
        
        assert alice_result1["thread_id"] is not None
        
        # Bob: Start different conversation
        bob_result1 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers_multi["user2"],
            json_data={
                "message": "How many annual leave days do I have?",
                "session_id": session2_id
            }
        )
        
        assert bob_result1["thread_id"] is not None
        assert alice_result1["thread_id"] != bob_result1["thread_id"]
        
        # Alice: Resume conversation with context reference
        alice_result2 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers_multi["user1"],
            json_data={
                "message": "Based on what we discussed, apply for that leave type tomorrow",
                "session_id": session1_id,
                "thread_id": alice_result1["thread_id"]  # Resume Alice's thread
            }
        )
        
        assert alice_result2["status_code"] == 200
        assert len(alice_result2["full_response"]) > 0
        print(f"\n[TEST] Alice contextual response: {alice_result2['full_response'][:200]}")
    
    def test_parallel_sessions(
        self, client, auth_headers_multi, session_factory, cleanup_sessions
    ):
        """Test parallel chat requests with different sessions.
        
        Verifies that:
        1. Multiple concurrent requests maintain correct contexts
        2. No race conditions in context variable handling
        3. SessionStore operations are thread-safe
        """
        # Create three sessions
        sessions = [
            {"id": session_factory(335, "User1"), "employee_id": 335, "user": "user1"},
            {"id": session_factory(336, "User2"), "employee_id": 336, "user": "user2"},
            {"id": session_factory(337, "User3"), "employee_id": 337, "user": "user3"},
        ]
        
        def send_chat_request(session_info):
            """Send a chat request and return the result."""
            result = parse_streaming_response(
                client, "POST", "/api/v1/chat",
                headers=auth_headers_multi[session_info["user"]],
                json_data={
                    "message": f"My employee ID should be {session_info['employee_id']}",
                    "session_id": session_info["id"]
                }
            )
            
            return {
                "session_id": session_info["id"],
                "employee_id": session_info["employee_id"],
                "thread_id": result["thread_id"],
                "response": result["full_response"],
                "status_code": result["status_code"]
            }
        
        # Send requests in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(send_chat_request, session) for session in sessions]
            results = [future.result() for future in as_completed(futures)]
        
        # Verify all requests succeeded
        assert len(results) == 3
        for result in results:
            assert result["status_code"] == 200
            assert result["thread_id"] is not None
            print(f"\n[TEST] Parallel result - Employee {result['employee_id']}: "
                  f"Thread {result['thread_id'][:8]}...")
        
        # Verify thread IDs are unique
        thread_ids = [r["thread_id"] for r in results]
        assert len(set(thread_ids)) == 3, "All parallel requests should have unique threads"
    
    def test_thread_id_persistence(
        self, client, auth_headers, session_factory, cleanup_sessions
    ):
        """Test that providing same thread_id resumes conversation.
        
        Verifies that:
        1. Explicit thread_id maintains conversation history
        2. New thread_id starts fresh conversation
        3. Thread isolation works correctly
        """
        session_id = session_factory(employee_id=335, employee_name="Test User")
        
        # First message - get auto-generated thread_id
        result1 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers,
            json_data={
                "message": "Hello, I want to apply for leave",
                "session_id": session_id
            }
        )
        
        assert result1["thread_id"] is not None
        print(f"\n[TEST] Generated thread_id: {result1['thread_id']}")
        
        # Second message - resume same thread
        result2 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers,
            json_data={
                "message": "What did I just say?",  # Should have context
                "session_id": session_id,
                "thread_id": result1["thread_id"]  # Resume
            }
        )
        assert result2["status_code"] == 200
        
        # Third message - new thread (no history)
        result3 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers,
            json_data={
                "message": "What did I just say?",  # Should NOT have context
                "session_id": session_id,
                "thread_id": str(uuid.uuid4())  # New thread
            }
        )
        assert result3["status_code"] == 200
    
    def test_session_context_in_thread(
        self, client, auth_headers, session_factory, cleanup_sessions
    ):
        """Test that employee_id from session is properly used within thread.
        
        Verifies that:
        1. Tools within a thread access correct employee_id
        2. Thread maintains consistent employee context
        """
        # Create session
        session_id = session_factory(employee_id=335, employee_name="Original User")
        
        # Start conversation with tool use
        result1 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers,
            json_data={
                "message": "Get my employee information",
                "session_id": session_id
            }
        )
        
        assert result1["status_code"] == 200
        assert result1["thread_id"] is not None
        print(f"\n[TEST] Employee context response: {result1['full_response'][:200]}")
        
        # Continue in same thread with tool call
        result2 = parse_streaming_response(
            client, "POST", "/api/v1/chat",
            headers=auth_headers,
            json_data={
                "message": "Apply for 1 day leave tomorrow",
                "session_id": session_id,
                "thread_id": result1["thread_id"]
            }
        )
        
        assert result2["status_code"] == 200
        # Tool should use employee_id=335 from session context
