"""Memory management endpoints for deleting LangGraph checkpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.database import User, ChatThread, ChatMessage
from app.core.config import settings
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import List
import psycopg

router = APIRouter(prefix="/memory", tags=["memory"])


def normalize_db_uri_for_psycopg(db_uri: str) -> str:
    """Normalize database URI to postgresql:// format for psycopg.
    
    Converts from any postgresql format to plain postgresql://
    and removes query parameters that psycopg doesn't need.
    """
    # Parse the URI
    parsed = urlparse(db_uri)
    
    # Convert any postgresql variant to plain postgresql://
    if parsed.scheme.startswith("postgresql"):
        # Remove driver specification (e.g., postgresql+asyncpg:// -> postgresql://)
        scheme = "postgresql"
    elif parsed.scheme == "postgres":
        scheme = "postgresql"
    else:
        raise ValueError(
            f"Unsupported database URI scheme. Expected postgresql:// or postgres://, "
            f"got: {parsed.scheme}"
        )
    
    # Parse and filter query parameters
    query_params = parse_qs(parsed.query)
    
    # Keep only essential query parameters (psycopg can handle sslmode)
    # Remove empty or None values
    filtered_params = {
        k: v for k, v in query_params.items() 
        if v and v[0]  # Keep non-empty params
    }
    
    # Reconstruct the URI
    new_query = urlencode(filtered_params, doseq=True) if filtered_params else ""
    
    normalized = urlunparse((
        scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    
    return normalized


def get_db_connection():
    """Get a database connection using psycopg."""
    # Normalize DB URI for psycopg (plain postgresql:// format)
    db_uri = normalize_db_uri_for_psycopg(settings.DATABASE_URL)
    
    return psycopg.connect(db_uri)


def get_user_thread_ids(user_id: int, db: Session) -> List[str]:
    """Get all thread_ids belonging to a user."""
    threads = db.query(ChatThread).filter(
        ChatThread.user_id == user_id
    ).all()
    return [thread.thread_id for thread in threads]


@router.delete("/{thread_id}")
async def delete_thread_memory(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete memory (checkpoints) and chat history for a specific thread ID.
    
    Deletes:
    1. LangGraph checkpoints (agent memory)
    2. Chat messages (conversation history)
    3. ChatThread record (if exists)
    
    This provides a complete reset for starting a new chat.
    
    Args:
        thread_id: The thread ID to delete memory for
        current_user: Authenticated user (from JWT token)
        db: Database session
    
    Returns:
        Success message with deletion counts
    """
    try:
        # Get counts before deletion
        messages_count = db.query(ChatMessage).filter(
            ChatMessage.thread_id == thread_id
        ).count()
        
        thread_exists = db.query(ChatThread).filter(
            ChatThread.thread_id == thread_id
        ).first() is not None
        
        # Delete from checkpoint tables and get counts
        # Note: We delete checkpoints directly without requiring a ChatThread to exist
        # LangGraph checkpoints can exist independently
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get counts before deletion
                cursor.execute(
                    "SELECT COUNT(*) FROM checkpoints WHERE thread_id = %s",
                    (thread_id,)
                )
                checkpoints_count = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id = %s",
                    (thread_id,)
                )
                checkpoint_writes_count = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT COUNT(*) FROM checkpoint_blobs WHERE thread_id = %s",
                    (thread_id,)
                )
                checkpoint_blobs_count = cursor.fetchone()[0]
                
                # Delete from all checkpoint-related tables
                cursor.execute(
                    "DELETE FROM checkpoints WHERE thread_id = %s",
                    (thread_id,)
                )
                cursor.execute(
                    "DELETE FROM checkpoint_writes WHERE thread_id = %s",
                    (thread_id,)
                )
                cursor.execute(
                    "DELETE FROM checkpoint_blobs WHERE thread_id = %s",
                    (thread_id,)
                )
                conn.commit()
        
        # Delete chat messages and thread from SQLAlchemy (using ORM)
        # Delete messages first (due to foreign key constraint)
        db.query(ChatMessage).filter(
            ChatMessage.thread_id == thread_id
        ).delete()
        
        # Delete thread
        db.query(ChatThread).filter(
            ChatThread.thread_id == thread_id
        ).delete()
        
        db.commit()
        
        return {
            "message": f"Memory and chat history deleted successfully for thread {thread_id}",
            "thread_id": thread_id,
            "deleted": {
                "checkpoints": checkpoints_count,
                "checkpoint_writes": checkpoint_writes_count,
                "checkpoint_blobs": checkpoint_blobs_count,
                "messages": messages_count,
                "thread": 1 if thread_exists else 0
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting thread memory: {str(e)}"
        )


@router.delete("")
async def delete_all_memory(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete all memory (checkpoints) for the current user.
    
    Only deletes checkpoints for threads belonging to the current user.
    Returns summary of deleted items.
    
    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
    
    Returns:
        Success message with summary of deleted items
    """
    try:
        # Get all thread_ids for the user
        user_thread_ids = get_user_thread_ids(current_user.id, db)
        
        if not user_thread_ids:
            return {
                "message": "No memory found for current user",
                "deleted": {
                    "checkpoints": 0,
                    "checkpoint_writes": 0,
                    "checkpoint_blobs": 0,
                    "threads": 0
                }
            }
        
        # Delete from checkpoint tables and get counts
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get counts before deletion
                placeholders = ','.join(['%s'] * len(user_thread_ids))
                
                cursor.execute(
                    f"SELECT COUNT(*) FROM checkpoints WHERE thread_id IN ({placeholders})",
                    tuple(user_thread_ids)
                )
                checkpoints_count = cursor.fetchone()[0]
                
                cursor.execute(
                    f"SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id IN ({placeholders})",
                    tuple(user_thread_ids)
                )
                checkpoint_writes_count = cursor.fetchone()[0]
                
                cursor.execute(
                    f"SELECT COUNT(*) FROM checkpoint_blobs WHERE thread_id IN ({placeholders})",
                    tuple(user_thread_ids)
                )
                checkpoint_blobs_count = cursor.fetchone()[0]
                
                # Delete from all checkpoint-related tables for user's threads
                cursor.execute(
                    f"DELETE FROM checkpoints WHERE thread_id IN ({placeholders})",
                    tuple(user_thread_ids)
                )
                cursor.execute(
                    f"DELETE FROM checkpoint_writes WHERE thread_id IN ({placeholders})",
                    tuple(user_thread_ids)
                )
                cursor.execute(
                    f"DELETE FROM checkpoint_blobs WHERE thread_id IN ({placeholders})",
                    tuple(user_thread_ids)
                )
                conn.commit()
        
        return {
            "message": "All memory deleted successfully for current user",
            "deleted": {
                "checkpoints": checkpoints_count,
                "checkpoint_writes": checkpoint_writes_count,
                "checkpoint_blobs": checkpoint_blobs_count,
                "threads": len(user_thread_ids)
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting all memory: {str(e)}"
        )

