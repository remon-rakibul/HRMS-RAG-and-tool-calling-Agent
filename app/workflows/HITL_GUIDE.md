# Human-in-the-Loop (HITL) Guide

This guide explains the Human-in-the-Loop (HITL) implementation in the HRMS Agent, which allows human oversight and approval before executing sensitive actions.

## Overview

Human-in-the-Loop enables the AI agent to pause execution at critical points and request human approval before proceeding. This is essential for:

- **Safety**: Prevent accidental or unauthorized actions (e.g., approving leave for the wrong employee)
- **Accuracy**: Allow users to verify extracted information before submission
- **Compliance**: Maintain audit trails for sensitive HR operations
- **Trust**: Build user confidence by showing what the AI will do before executing

## Architecture

```
User Request → LangGraph Workflow → Tool Execution
                                         ↓
                              interrupt() pauses execution
                                         ↓
                              Frontend shows ApprovalCard
                                         ↓
                              User approves/rejects/edits
                                         ↓
                              Command(resume=data) continues
                                         ↓
                              Tool completes with user's input
```

## HITL Patterns Implemented

### Pattern 1: Tool-Level Approval (Single Step)

**Used by**: `apply_for_leave`, `apply_for_attendance`, `apply_leave_for_employee`

Before executing a tool, the agent pauses and shows the user what action will be taken:

```python
from langgraph.types import interrupt
from app.workflows.prompt_loader import should_require_approval

if should_require_approval("apply_for_leave"):
    confirmation = interrupt({
        "action": "leave_application",
        "message": "Please confirm this leave application:",
        "details": {
            "employee_id": 335,
            "leave_type": "Annual Leave",
            "period": "2026-02-01 to 2026-02-03",
            "days": 3,
            "reason": "Family vacation"
        },
        "editable_fields": ["reason", "total_days"],
        "current_values": {"reason": "Family vacation", "total_days": 3},
        "options": ["approve", "reject", "edit"]
    })
    
    if confirmation.get("action") == "reject":
        return "❌ Leave application cancelled by user."
    
    # Apply any edits from user
    if confirmation.get("reason"):
        reason = confirmation["reason"]
```

**Frontend Display:**
- Shows action details in an ApprovalCard
- User can approve, reject, or edit values
- Editable fields can be modified before approval

### Pattern 2: Multi-Step Approval

**Used by**: `approve_leave_for_employee`, `approve_attendance_for_employee`

For admin actions, a two-step verification ensures the correct employee and action:

**Step 1: Verify Employee**
```python
if should_use_multi_step("approve_leave_for_employee"):
    verification = interrupt({
        "action": "verify_employee",
        "step": 1,
        "total_steps": 2,
        "message": f"Found employee: {found_name} (ID: {employee_id})",
        "question": "Is this the correct employee?",
        "details": {"employee_id": employee_id, "employee_name": found_name},
        "options": ["confirm", "reject"]
    })
    
    if verification.get("action") != "confirm":
        return "❌ Employee verification cancelled."
```

**Step 2: Confirm Action**
```python
    final_approval = interrupt({
        "action": "confirm_leave_approval",
        "step": 2,
        "total_steps": 2,
        "message": "Please confirm leave approval details:",
        "details": {
            "employee": found_name,
            "leave_period": "2026-02-01 to 2026-02-03",
            "days": 3,
            "leave_type": "Annual Leave",
            "reason": "Family vacation"
        },
        "editable_fields": ["remarks"],
        "current_values": {"remarks": "Approved"},
        "options": ["approve", "reject"]
    })
```

### Pattern 3: Cancel/Reject Actions

**Used by**: `cancel_leave_for_employee`, `cancel_attendance_for_employee`

Similar to approval but for destructive actions, ensuring the user understands the consequences.

## Configuration

### prompts.json Settings

All HITL settings are configured in `app/workflows/prompts.json`:

```json
{
  "hitl_settings": {
    "enabled": true,
    "require_approval_for": [
      "apply_for_leave",
      "approve_leave_for_employee",
      "cancel_leave_for_employee",
      "apply_for_attendance",
      "approve_attendance_for_employee",
      "cancel_attendance_for_employee",
      "apply_leave_for_employee"
    ],
    "multi_step_approval_for": [
      "approve_leave_for_employee",
      "approve_attendance_for_employee"
    ],
    "review_documents": false,
    "validate_inputs": true,
    "use_node_level_gate": false,
    "timeout_seconds": 300
  }
}
```

### Configuration Options

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | `true` | Master switch for all HITL features |
| `require_approval_for` | array | [...] | List of tool names requiring approval |
| `multi_step_approval_for` | array | [...] | Tools requiring multi-step verification |
| `review_documents` | boolean | `false` | Show retrieved documents for review before answering |
| `validate_inputs` | boolean | `true` | Validate tool inputs before execution |
| `use_node_level_gate` | boolean | `false` | Require approval before entering tools node |
| `timeout_seconds` | number | `300` | Auto-reject after timeout (5 minutes) |

### Disabling HITL

To disable all HITL features:

```json
{
  "hitl_settings": {
    "enabled": false
  }
}
```

To disable HITL for specific tools, remove them from the `require_approval_for` array.

## API Endpoints

### Chat Endpoint (Initial Request)

```bash
POST /api/v1/chat
Content-Type: application/json

{
  "message": "Apply for leave tomorrow",
  "thread_id": "abc123",
  "session_id": "xyz789"
}
```

**Response (SSE Stream):**
```
data: {"type": "interrupt", "interrupt_data": {...}, "thread_id": "abc123"}
```

### Resume Endpoint (After Approval)

```bash
POST /api/v1/chat/resume
Content-Type: application/json

{
  "thread_id": "abc123",
  "session_id": "xyz789",
  "resume_data": {
    "action": "approve",
    "reason": "Updated reason text"
  }
}
```

**Response (SSE Stream):**
```
data: {"type": "token", "content": "Done! I've applied..."}
data: {"type": "done", "content": "..."}
```

## Frontend Integration

### Interrupt Data Structure

When an interrupt occurs, the frontend receives:

```typescript
interface InterruptData {
  action: string;           // e.g., "leave_application", "verify_employee"
  message: string;          // Human-readable message
  step?: number;            // Current step (for multi-step)
  total_steps?: number;     // Total steps (for multi-step)
  details: Record<string, any>;  // Action details to display
  editable_fields?: string[];    // Fields user can modify
  current_values?: Record<string, any>;  // Current field values
  question?: string;        // Question to ask user
  options: string[];        // Available actions (e.g., ["approve", "reject"])
}
```

### ApprovalCard Component

The frontend displays interrupts using `ApprovalCard.tsx`:

- Shows action details in a card layout
- Displays step indicator for multi-step flows (e.g., "Step 1 of 2")
- Renders editable fields as input controls
- Provides action buttons based on `options`

### useChat Hook Integration

```typescript
const { 
  isAwaitingApproval,  // True when waiting for user response
  pendingInterrupt,     // Current interrupt data
  resumeWithResponse    // Function to resume with user's decision
} = useChat(threadId, sessionId);

// Handle approval
const handleApprove = (editedValues) => {
  resumeWithResponse({ action: "approve", ...editedValues });
};

// Handle rejection
const handleReject = () => {
  resumeWithResponse({ action: "reject" });
};
```

## Implementation Details

### Tool-Level Implementation

Tools use LangGraph's `interrupt()` function to pause execution:

```python
from langgraph.types import interrupt
from langgraph.errors import GraphInterrupt

def my_tool():
    try:
        # ... tool logic ...
        
        confirmation = interrupt({
            "action": "my_action",
            "message": "Please confirm:",
            "options": ["approve", "reject"]
        })
        
        if confirmation.get("action") != "approve":
            return "Cancelled"
        
        # Continue with action
        
    except GraphInterrupt:
        # IMPORTANT: Re-raise interrupt exceptions
        raise
    except Exception as e:
        return f"Error: {e}"
```

> **Critical**: Always add `except GraphInterrupt: raise` before any generic `except Exception` handlers. Otherwise, the interrupt exception will be caught and the HITL flow will break.

### Prompt Loader Helpers

`app/workflows/prompt_loader.py` provides helper functions:

```python
from app.workflows.prompt_loader import (
    should_require_approval,  # Check if tool needs approval
    should_use_multi_step,    # Check if tool needs multi-step
    is_hitl_enabled           # Check if HITL is enabled globally
)

if should_require_approval("apply_for_leave"):
    # Request approval
    
if should_use_multi_step("approve_leave_for_employee"):
    # Use two-step verification
```

### Backend Stream Handling

`chat_service.py` detects interrupts during streaming:

```python
# Detect interrupts from HITL patterns
if event_type == "on_chain_end":
    output = data.get("output", {})
    
    if isinstance(output, dict) and "__interrupt__" in output:
        interrupt_list = output["__interrupt__"]
        interrupt_data = interrupt_list[0].value
        
        yield {
            "type": "interrupt",
            "interrupt_data": interrupt_data,
            "thread_id": thread_id
        }
        return  # Stop streaming, wait for resume
```

## Adding HITL to New Tools

### Step 1: Import Required Functions

```python
from langgraph.types import interrupt
from langgraph.errors import GraphInterrupt
from app.workflows.prompt_loader import should_require_approval
```

### Step 2: Add Approval Check

```python
@tool_registry.register
def my_new_tool(param1: str, param2: int) -> str:
    # Check if approval is required
    if should_require_approval("my_new_tool"):
        confirmation = interrupt({
            "action": "my_action",
            "message": "Please confirm this action:",
            "details": {
                "param1": param1,
                "param2": param2
            },
            "options": ["approve", "reject"]
        })
        
        if confirmation.get("action") != "approve":
            return "❌ Action cancelled."
    
    # Continue with tool logic
```

### Step 3: Handle Exceptions Properly

```python
    try:
        # Tool logic with API calls
        response = httpx.post(...)
    except GraphInterrupt:
        raise  # Always re-raise interrupts
    except Exception as e:
        return f"Error: {e}"
```

### Step 4: Add to Configuration

In `prompts.json`:

```json
{
  "hitl_settings": {
    "require_approval_for": [
      "my_new_tool",
      // ... existing tools
    ]
  }
}
```

## Troubleshooting

### Interrupt Not Detected

**Symptom**: Tool executes without showing approval UI

**Causes & Solutions**:
1. Tool not in `require_approval_for` → Add to config
2. `hitl_settings.enabled` is false → Set to true
3. `should_require_approval()` not called → Add check in tool

### Multi-Step Flow Breaks After First Step

**Symptom**: First approval works, but second step never appears

**Cause**: `except Exception` handler catching `GraphInterrupt`

**Solution**: Add this before generic exception handlers:
```python
except GraphInterrupt:
    raise
```

### Frontend Not Showing ApprovalCard

**Symptom**: Backend logs show interrupt, but UI doesn't update

**Causes & Solutions**:
1. Check `onInterrupt` callback in `sendChatMessage`
2. Verify `InterruptPayload` type matches backend structure
3. Check browser console for errors

### Resume Fails with "Invalid Thread ID"

**Symptom**: Approval fails with thread error

**Cause**: Thread ID mismatch or expired checkpoint

**Solution**: Ensure same `thread_id` is used for initial request and resume

## Best Practices

1. **Be Specific**: Include all relevant details in interrupt data so users can make informed decisions

2. **Allow Edits**: For user-facing tools, include editable fields so users can correct AI's interpretation

3. **Clear Options**: Use action verbs that match the context ("approve"/"reject" for approvals, "confirm"/"cancel" for confirmations)

4. **Multi-Step for Admin**: Always use multi-step for admin actions that affect other employees

5. **Timeout Handling**: Consider implementing frontend timeout handling for the 300-second limit

6. **Error Messages**: Provide clear cancellation messages that explain what was not done

## Related Files

- `app/workflows/prompts.json` - HITL configuration
- `app/workflows/prompt_loader.py` - HITL helper functions
- `app/services/chat_service.py` - Interrupt detection and resume handling
- `app/api/v1/endpoints/chat.py` - Resume API endpoint
- `frontend/src/hooks/useChat.ts` - Frontend interrupt handling
- `frontend/src/components/ApprovalCard.tsx` - Approval UI component
