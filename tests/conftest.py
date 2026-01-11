"""Pytest configuration and fixtures."""
import pytest
import os
import asyncio
import uuid
from typing import Generator, Dict
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables before importing app
# Load real API key from .env for integration tests
from dotenv import load_dotenv
load_dotenv()

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", 
    os.getenv("DATABASE_URL", "postgresql://postgres:123456@localhost:5432/postgres?sslmode=disable")
)
# Use real OpenAI API key for integration tests (not "test-key")
if "OPENAI_API_KEY" not in os.environ or os.environ["OPENAI_API_KEY"] == "test-key":
    # Try to load from .env if not set
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not set - tests may fail")

os.environ["SECRET_KEY"] = os.getenv("SECRET_KEY", "test-secret-key-for-testing")
os.environ["USER_AGENT"] = os.getenv("USER_AGENT", "RAG-Pipeline-Test/1.0")
os.environ["DEBUG"] = "true"

from app.core.database import Base, get_db
from app.main import app
from app.models.agent_session import get_session, delete_session
from app.models.database import AgentSession


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session."""
    # Use in-memory SQLite for faster tests (if not using PostgreSQL)
    # For PostgreSQL tests, use the actual database
    database_url = os.getenv("TEST_DATABASE_URL")
    
    if database_url and "postgresql" in database_url:
        # Use PostgreSQL
        engine = create_engine(database_url, poolclass=StaticPool)
    else:
        # Use in-memory SQLite for unit tests
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client."""
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Create authentication headers for testing."""
    # Register a test user
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpassword123"
        }
    )
    
    # Login to get token
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
            "password": "testpassword123"
        }
    )
    
    if login_response.status_code == 200:
        token = login_response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.fixture
def auth_headers_multi(client):
    """Create authentication headers for multiple test users.
    
    Returns a dict with user identifiers as keys and their auth headers as values.
    """
    users = {
        "user1": {"email": "user1@example.com", "password": "testpass123"},
        "user2": {"email": "user2@example.com", "password": "testpass123"},
        "user3": {"email": "user3@example.com", "password": "testpass123"},
    }
    
    headers = {}
    for user_id, credentials in users.items():
        # Register user
        client.post("/api/v1/auth/register", json=credentials)
        
        # Login to get token
        login_response = client.post("/api/v1/auth/login", json=credentials)
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            headers[user_id] = {"Authorization": f"Bearer {token}"}
    
    return headers


@pytest.fixture
def session_factory(client, auth_headers):
    """Factory fixture for creating HRMS sessions with different employee IDs.
    
    Returns a callable that creates and initializes a session.
    Usage: session_id = session_factory(employee_id=335, employee_name="John Doe")
    """
    created_sessions = []
    
    def _create_session(employee_id: int, employee_name: str) -> str:
        session_id = str(uuid.uuid4())
        response = client.post(
            "/api/v1/agent/session-init",
            json={
                "sessionId": session_id,
                "employeeId": employee_id,
                "employeeName": employee_name
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to create session: {response.json()}"
        created_sessions.append(session_id)
        return session_id
    
    yield _create_session
    
    # Cleanup: delete all created sessions
    for session_id in created_sessions:
        try:
            client.delete(f"/api/v1/agent/session/{session_id}", headers=auth_headers)
        except:
            pass


@pytest.fixture
def cleanup_sessions(db_session):
    """Cleanup fixture to clear agent sessions from database after each test."""
    yield
    # Clear all sessions from the database after test
    db_session.query(AgentSession).delete()
    db_session.commit()


@pytest.fixture
async def cleanup_threads():
    """Cleanup fixture to clear LangGraph checkpoints after each test.
    
    Note: This is an async fixture that clears checkpoint data from PostgreSQL.
    """
    yield
    
    # Clean up checkpoint data
    try:
        from app.workflows.rag_graph import get_checkpointer
        checkpointer = await get_checkpointer()
        # Note: AsyncPostgresSaver doesn't have a clear method by default
        # In production, you might want to delete specific thread checkpoints
        # For now, we'll rely on test database isolation
    except Exception as e:
        print(f"Warning: Could not cleanup checkpoints: {e}")


@pytest.fixture
def parse_sse_response():
    """Helper fixture to parse Server-Sent Events (SSE) streaming responses.
    
    Returns a callable that parses SSE response and extracts chunks.
    """
    def _parse(response_text: str) -> list:
        """Parse SSE response into a list of data chunks."""
        chunks = []
        for line in response_text.split('\n'):
            if line.startswith('data: '):
                import json
                try:
                    data = json.loads(line[6:])  # Remove 'data: ' prefix
                    chunks.append(data)
                except json.JSONDecodeError:
                    continue
        return chunks
    
    return _parse

