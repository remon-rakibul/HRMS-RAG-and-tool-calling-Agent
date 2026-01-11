# Employee Context Flow

## How employee_id gets from HRMS frontend to the leave application tool

```
HRMS Frontend
    ↓ (sends employee_id in chat request)
Chat API Endpoint (/api/v1/chat)
    ↓ (extracts employee_id from request)
Chat Service (stream_chat)
    ↓ (sets in context variable using set_employee_id())
Context Module (contextvars)
    ↓ (stored in thread-local storage)
Leave Apply Tool (apply_for_leave)
    ↓ (reads using get_employee_id())
HRMS API (leave application submitted for correct employee)
```

## Usage

### From HRMS Frontend:
```javascript
POST /api/v1/chat
{
  "message": "Apply for 2 days leave from December 10th",
  "employee_id": 408,  // <-- Pass the logged-in employee's ID
  "thread_id": "optional-thread-id"
}
```

### From Agent:
The tool automatically picks up `employee_id` from context:
```python
# Tool will use employee_id=408 automatically
"Apply for leave from December 10th for 2 days"
```

## Priority Order

The tool uses employee_id in this order:
1. **From context** (set by chat service) ← Primary method
2. **From parameter** (explicitly passed to tool)
3. **Default fallback** (335) ← Only if none provided

## Files Modified

1. `app/workflows/context.py` - Context management module (NEW)
2. `app/models/schemas.py` - Added `employee_id` field to `ChatRequest`
3. `app/api/v1/endpoints/chat.py` - Passes `employee_id` to chat service
4. `app/services/chat_service.py` - Sets context before streaming
5. `app/workflows/tools/leave_apply.py` - Reads from context

## Testing

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Apply for 1 day sick leave tomorrow",
    "employee_id": 408
  }'
```

The tool will apply leave for employee 408, not the default 335!

