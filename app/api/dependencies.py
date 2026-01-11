"""API dependencies for authentication and database."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token, is_token_blacklisted, TOKEN_TYPE_ACCESS
from app.models.database import User


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    
    # Handle case where "Bearer " is accidentally included in token (e.g., from Postman)
    if token.startswith("Bearer "):
        token = token[7:]  # Remove "Bearer " prefix
        print(f"[Auth] Warning: Token had 'Bearer ' prefix, removed it", flush=True)
    
    # Log token for debugging (first 20 chars only for security)
    print(f"[Auth] Attempting to validate token: {token[:20]}...", flush=True)
    
    payload = decode_access_token(token)
    
    if payload is None:
        print(f"[Auth] Token validation failed - decode_access_token returned None", flush=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials. Token may be expired or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if token is blacklisted (logout)
    if is_token_blacklisted(token, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify token type
    token_type = payload.get("type")
    if token_type != TOKEN_TYPE_ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Access token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    # Validate user_id - it's stored as a string in the token, convert to int
    try:
        user_id = int(user_id_raw)  # Convert string to int for database lookup
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    return user

