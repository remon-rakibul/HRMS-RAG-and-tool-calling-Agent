"""SQLAlchemy database models."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    chat_threads = relationship("ChatThread", back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    """Document metadata model."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source_type = Column(String, nullable=False)  # 'url', 'pdf', 'docx', etc.
    source_path = Column(String, nullable=False)  # URL or file path
    chunk_count = Column(Integer, default=0)
    document_ids = Column(Text)  # JSON array of PGVector document IDs
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="documents")


class ChatThread(Base):
    """Chat thread model."""
    __tablename__ = "chat_threads"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    thread_id = Column(String, unique=True, nullable=False, index=True)  # LangGraph thread_id
    title = Column(String, nullable=True)  # First message or user-defined title
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="chat_threads")
    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Chat message model."""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, ForeignKey("chat_threads.thread_id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'tool'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    thread = relationship("ChatThread", back_populates="messages")


class TokenBlacklist(Base):
    """Token blacklist model for logout functionality."""
    __tablename__ = "token_blacklist"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentSession(Base):
    """Agent session model for HRMS integration.
    
    Stores session information from HRMS frontend to be used by agent frontend.
    Each session maps to an employee and allows the agent to perform actions
    on behalf of that employee.
    """
    __tablename__ = "agent_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    employee_id = Column(Integer, nullable=False, index=True)
    employee_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)  # Optional expiration
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return False
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        # Ensure expires_at is timezone-aware for comparison
        if self.expires_at.tzinfo is None:
            # If expires_at is naive, assume it's UTC
            expires_at_aware = self.expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at_aware = self.expires_at
        return now > expires_at_aware

