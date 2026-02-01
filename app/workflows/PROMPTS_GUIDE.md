# Prompts Configuration Guide

## Overview

All system messages and prompts are now stored in `prompts.json` for easy modification without changing code.

## File Location

```
app/workflows/prompts.json
```

## Structure

```json
{
  "system_messages": {
    "generate_query_or_respond": {
      "template": "...",
      "description": "..."
    }
  },
  "prompts": {
    "grade_documents": { "template": "...", "description": "..." },
    "rewrite_question": { "template": "...", "description": "..." },
    "generate_answer": { "template": "...", "description": "..." }
  },
  "retriever_tool": {
    "name": "...",
    "description": "..."
  },
  "settings": {
    "default_model": "...",
    "default_temperature": 0,
    "default_k": 5,
    "streaming_enabled": true
  }
}
```

## How to Modify Prompts

### 1. Edit `prompts.json`

Open the file and modify any template:

```json
{
  "prompts": {
    "generate_answer": {
      "template": "You are a helpful assistant. Answer concisely.\nQuestion: {question}\nContext: {context}",
      "description": "Your custom prompt here"
    }
  }
}
```

### 2. Restart Server

```bash
# Stop the server (Ctrl+C)
# Then restart
python run.py
# or
uvicorn app.main:app --reload
```

**Note:** Prompts are loaded at startup. Changes require a restart.

## Available Prompts

### System Messages

#### `generate_query_or_respond`
- **Purpose:** Guides LLM to focus on current question in multi-turn conversations
- **Variables:** `{current_question}` - The latest user question
- **When Used:** Before LLM decides whether to retrieve or respond directly

### Prompts

#### `grade_documents`
- **Purpose:** Assess if retrieved documents are relevant to the question
- **Variables:** 
  - `{question}` - User's question
  - `{context}` - Retrieved document content
- **Output:** "yes" or "no"
- **When Used:** After retrieval, before generating answer

#### `rewrite_question`
- **Purpose:** Improve question for better semantic search
- **Variables:** `{question}` - Original user question
- **When Used:** When documents are not relevant, to refine the query

#### `generate_answer`
- **Purpose:** Generate final answer from retrieved context
- **Variables:**
  - `{question}` - User's question
  - `{context}` - Retrieved document content
- **When Used:** After documents are graded as relevant

## Template Variables

| Variable | Description | Used In |
|----------|-------------|---------|
| `{current_question}` | Latest user question | `generate_query_or_respond` system message |
| `{question}` | User question | All prompts |
| `{context}` | Retrieved documents | `grade_documents`, `generate_answer` |

## Settings

### Model Configuration

```json
{
  "settings": {
    "default_model": "gpt-4o-mini",
    "default_temperature": 0,
    "default_k": 5,
    "streaming_enabled": true
  }
}
```

- **default_model**: LLM model to use (e.g., "gpt-4o-mini", "gpt-4o")
- **default_temperature**: Creativity level (0 = deterministic, 1 = creative)
- **default_k**: Number of documents to retrieve (default: 5)
- **streaming_enabled**: Enable token-by-token streaming

## Retriever Tool Configuration

```json
{
  "retriever_tool": {
    "name": "retrieve_documents",
    "description": "Search and return information from ingested documents. Use this tool when you need to find specific information from the user's document collection."
  }
}
```

- **name**: Tool name shown to LLM
- **description**: How LLM decides when to use retrieval

## Human-in-the-Loop (HITL) Configuration

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

### HITL Settings Explained

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | `true` | Master switch for all HITL features |
| `require_approval_for` | array | [...] | Tool names that require user approval before execution |
| `multi_step_approval_for` | array | [...] | Tools requiring multi-step verification (e.g., verify employee first) |
| `review_documents` | boolean | `false` | Show retrieved documents for user review before answering |
| `validate_inputs` | boolean | `true` | Validate tool inputs before execution |
| `use_node_level_gate` | boolean | `false` | Require approval before entering tools node (graph-level) |
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

To disable HITL for a specific tool, remove it from `require_approval_for`.

### Adding HITL to New Tools

1. Add the tool name to `require_approval_for`
2. If multi-step needed, also add to `multi_step_approval_for`
3. Implement `interrupt()` in the tool (see [HITL_GUIDE.md](HITL_GUIDE.md))

For detailed HITL implementation, see [HITL_GUIDE.md](HITL_GUIDE.md)

## Example Modifications

### Make Answers More Detailed

```json
{
  "prompts": {
    "generate_answer": {
      "template": "You are an expert assistant. Provide a comprehensive answer using the retrieved context.\n\nQuestion: {question}\n\nContext: {context}\n\nAnswer in detail with examples when possible:",
      "description": "Detailed answer generation"
    }
  }
}
```

### Change Model

```json
{
  "settings": {
    "default_model": "gpt-4o",
    "default_temperature": 0.3
  }
}
```

### Customize System Message

```json
{
  "system_messages": {
    "generate_query_or_respond": {
      "template": "You are a helpful assistant. The user's current question is: '{current_question}'. Answer this question specifically, ignoring previous conversation unless directly relevant.",
      "description": "Custom system message"
    }
  }
}
```

## Validation

The system validates:
- ✅ JSON syntax
- ✅ Required fields exist
- ✅ Template variables match usage

If validation fails, you'll see clear error messages.

## Hot Reload (Future Enhancement)

Currently requires server restart. Future versions may support hot reload.

## Best Practices

1. **Backup Before Changes**: Copy `prompts.json` before major modifications
2. **Test Incrementally**: Change one prompt at a time
3. **Keep Variables**: Don't remove `{question}`, `{context}`, `{current_question}` - they're required
4. **Clear Instructions**: Write prompts as if instructing a human
5. **Test After Changes**: Restart server and test with real queries

## Troubleshooting

### Error: "Prompts file not found"
- **Solution**: Ensure `prompts.json` exists in `app/workflows/` directory

### Error: "Invalid JSON"
- **Solution**: Validate JSON syntax using a JSON validator or Python:
  ```python
  import json
  with open('prompts.json') as f:
      json.load(f)  # Will raise error if invalid
  ```

### Error: "Template variable not found"
- **Solution**: Ensure all variables in template exist (e.g., `{question}`, `{context}`)

### Prompts Not Updating
- **Solution**: Restart the server after modifying `prompts.json`

## Code Usage

### Prompt Functions

```python
from app.workflows.prompt_loader import get_prompt, get_system_message

# Get a prompt
prompt = get_prompt("generate_answer", question="...", context="...")

# Get system message
sys_msg = get_system_message("generate_query_or_respond", current_question="...")
```

### HITL Functions

```python
from app.workflows.prompt_loader import (
    is_hitl_enabled,
    should_require_approval,
    should_use_multi_step,
    should_review_documents,
    should_validate_inputs,
    should_use_node_level_gate,
    get_hitl_timeout
)

# Check if HITL is globally enabled
if is_hitl_enabled():
    print("HITL is enabled")

# Check if a tool requires approval
if should_require_approval("apply_for_leave"):
    # Show approval UI
    pass

# Check if tool needs multi-step approval
if should_use_multi_step("approve_leave_for_employee"):
    # Step 1: Verify employee
    # Step 2: Confirm action
    pass

# Get HITL timeout
timeout = get_hitl_timeout()  # Returns 300 (seconds)
```

## File Format

- **Format**: JSON (UTF-8 encoding)
- **Indentation**: 2 spaces (for readability)
- **Comments**: Not supported in JSON (use `description` field instead)

