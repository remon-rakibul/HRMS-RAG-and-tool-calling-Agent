"""Agent session management endpoints.

These endpoints allow the HRMS backend to initialize and manage
agent sessions for authenticated users.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.database import User
from app.models.agent_session import (
    SessionInitRequest,
    SessionInitResponse,
    create_session,
    get_session as get_session_context,
    delete_session as delete_session_context
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/session-init", response_model=SessionInitResponse)
async def initialize_session(
    request: SessionInitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initialize an agent session with HRMS user context.
    
    This endpoint is called by the HRMS backend when a user opens
    the agent chat. It stores the user's context so the agent can
    perform actions on their behalf.
    
    The HRMS backend should call this endpoint before the user
    starts chatting with the agent.
    
    Requires authentication via JWT Bearer token.
    
    Args:
        request: User context from HRMS backend (AppUser data)
        current_user: Authenticated user (from JWT token)
        db: Database session
        
    Returns:
        SessionInitResponse with success status and session ID
    """
    try:
        # Convert request to internal context model
        context = request.to_context()
        
        # Store in database
        session = create_session(
            db=db,
            session_id=context.session_id,
            employee_id=context.employee_id,
            employee_name=context.employee_name,
            ttl_hours=24  # 24 hour session lifetime
        )
        
        print(f"[Agent] Session initialized for employee: {context.employee_name} "
              f"(ID: {context.employee_id}, Session: {context.session_id})", flush=True)
        
        return SessionInitResponse(
            success=True,
            message="Session initialized",
            sessionId=context.session_id
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[Agent] Session init error: {str(e)}", flush=True)
        print(f"[Agent] Traceback: {error_trace}", flush=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize session: {str(e)}"
        )


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get session context (for debugging/validation).
    
    Requires authentication via JWT Bearer token.
    
    Args:
        session_id: The session ID to look up
        current_user: Authenticated user (from JWT token)
        db: Database session
        
    Returns:
        Session context if found
    """
    context = get_session_context(db=db, session_id=session_id)
    
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired"
        )
    
    return {
        "session_id": context.session_id,
        "employee_id": context.employee_id,
        "employee_name": context.employee_name
    }


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete/invalidate a session.
    
    Called when user logs out or session should be terminated.
    Requires authentication via JWT Bearer token.
    
    Args:
        session_id: The session ID to delete
        current_user: Authenticated user (from JWT token)
        db: Database session
        
    Returns:
        Success status
    """
    deleted = delete_session_context(db=db, session_id=session_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return {"success": True, "message": "Session deleted"}

