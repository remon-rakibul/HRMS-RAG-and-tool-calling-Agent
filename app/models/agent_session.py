"""Agent session models for HRMS integration.

This module provides session management for tracking user context
from the HRMS backend during agent interactions.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.database import AgentSession as AgentSessionModel


class AgentSessionContext(BaseModel):
    """User context received from HRMS backend.
    
    Contains the user information needed for the agent to
    perform actions on behalf of the logged-in HRMS user.
    """
    session_id: str = Field(..., description="Unique session identifier")
    employee_id: int = Field(..., description="HRMS employee ID for API calls")
    employee_name: str = Field(..., description="Employee's full name")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "abc123-def456",
                "employee_id": 335,
                "employee_name": "John Doe"
            }
        }


class SessionInitRequest(BaseModel):
    """Request model for session initialization from HRMS backend.
    
    Minimal payload: only sessionId, employeeId, employeeName.
    """
    sessionId: str = Field(..., description="Unique session identifier")
    employeeId: int = Field(..., description="HRMS employee ID")
    employeeName: str = Field(..., description="Employee's full name")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "sessionId": "abc123-def456",
                "employeeId": 335,
                "employeeName": "John Doe"
            }
        }
    
    def to_context(self) -> AgentSessionContext:
        """Convert request to internal context model."""
        return AgentSessionContext(
            session_id=self.sessionId,
            employee_id=self.employeeId,
            employee_name=self.employeeName,
        )


class SessionInitResponse(BaseModel):
    """Response model for session initialization."""
    success: bool = True
    message: str = "Session initialized"
    sessionId: str = Field(...)
    
    class Config:
        populate_by_name = True


# Database-based session management functions

def create_session(
    db: Session,
    session_id: str,
    employee_id: int,
    employee_name: str,
    ttl_hours: int = 24
) -> AgentSessionModel:
    """Create a new agent session in the database.
    
    Args:
        db: Database session
        session_id: Unique session identifier
        employee_id: HRMS employee ID
        employee_name: Employee's full name
        ttl_hours: Session lifetime in hours (default: 24)
        
    Returns:
        Created AgentSession model instance
    """
    expires_at = None
    if ttl_hours > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    
    # Check if session already exists and update it, or create new
    existing = db.query(AgentSessionModel).filter(
        AgentSessionModel.session_id == session_id
    ).first()
    
    if existing:
        existing.employee_id = employee_id
        existing.employee_name = employee_name
        existing.expires_at = expires_at
        db.commit()
        db.refresh(existing)
        return existing
    
    session = AgentSessionModel(
        session_id=session_id,
        employee_id=employee_id,
        employee_name=employee_name,
        expires_at=expires_at
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> Optional[AgentSessionContext]:
    """Retrieve a session context from the database.
    
    Args:
        db: Database session
        session_id: Session identifier to look up
        
    Returns:
        AgentSessionContext if found and not expired, None otherwise
    """
    session = db.query(AgentSessionModel).filter(
        AgentSessionModel.session_id == session_id
    ).first()
    
    if session is None:
        return None
    
    # Check if session has expired
    if session.is_expired():
        # Delete expired session
        db.delete(session)
        db.commit()
        return None
    
    # Convert to Pydantic model
    return AgentSessionContext(
        session_id=session.session_id,
        employee_id=session.employee_id,
        employee_name=session.employee_name,
        created_at=session.created_at
    )

    
def refresh_session(db: Session, session_id: str, ttl_hours: int = 24) -> bool:
    """Refresh/extend session expiration time.
    
    This function extends the session expiration time, keeping the session
    alive as long as the user is actively using the system. Should be called
    whenever a session is accessed during active use (e.g., on each chat message).
    
    Args:
        db: Database session
        session_id: Session identifier to refresh
        ttl_hours: New TTL in hours (default: 24)
        
    Returns:
        True if session was refreshed, False if not found or expired
    """
    session = db.query(AgentSessionModel).filter(
        AgentSessionModel.session_id == session_id
    ).first()
    
    if session is None:
        return False
    
    # Don't refresh if already expired
    if session.is_expired():
        return False
    
    # Extend expiration time
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    session.expires_at = expires_at
    db.commit()
    db.refresh(session)
    return True


def delete_session(db: Session, session_id: str) -> bool:
    """Delete a session from the database.
    
    Args:
        db: Database session
        session_id: Session identifier to delete
        
    Returns:
        True if session was deleted, False if not found
    """
    session = db.query(AgentSessionModel).filter(
        AgentSessionModel.session_id == session_id
    ).first()
    
    if session is None:
        return False
    
    db.delete(session)
    db.commit()
    return True


def cleanup_expired_sessions(db: Session) -> int:
    """Remove all expired sessions from the database.
    
    Args:
        db: Database session
        
        Returns:
            Number of sessions removed
        """
    now = datetime.now(timezone.utc)
    expired = db.query(AgentSessionModel).filter(
        AgentSessionModel.expires_at.isnot(None),
        AgentSessionModel.expires_at < now
    ).all()
    
    count = len(expired)
    for session in expired:
        db.delete(session)
    
    db.commit()
    return count

