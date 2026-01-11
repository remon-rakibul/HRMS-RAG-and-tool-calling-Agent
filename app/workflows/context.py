"""Context management for workflow tools.

This module provides a way to pass user context (like employee_id)
from the API endpoint through to the workflow tools.
"""

from contextvars import ContextVar
from typing import Optional

# Context variable to store employee ID during tool execution
_employee_id_context: ContextVar[Optional[int]] = ContextVar('employee_id', default=None)


def set_employee_id(employee_id: Optional[int]) -> None:
    """Set employee ID in context for tools to access."""
    _employee_id_context.set(employee_id)


def get_employee_id() -> Optional[int]:
    """Get employee ID from context."""
    return _employee_id_context.get()


def get_user_context():
    """Get full user context (for backward compatibility with hrms_queries).
    
    Returns a simple object with employee_id attribute.
    Note: This is a simplified version. Full context would include more fields.
    """
    employee_id = get_employee_id()
    if employee_id is None:
        return None
    
    # Return a simple object with basic attributes
    class UserContext:
        def __init__(self, employee_id):
            self.employee_id = employee_id
            self.employee_name = "Unknown"  # Would come from HRMS session
            self.username = "Unknown"
            self.role_name = "Unknown"
            self.company_id = None
            self.organization_id = None
    
    return UserContext(employee_id)


def get_company_id() -> Optional[int]:
    """Get company ID from context (for backward compatibility).
    
    Returns None for now. Would be set from HRMS session in the future.
    """
    return None


def clear_context() -> None:
    """Clear all context variables."""
    _employee_id_context.set(None)
