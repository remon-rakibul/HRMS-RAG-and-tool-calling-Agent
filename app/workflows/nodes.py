"""LangGraph workflow node functions extracted from graph.py."""
from langgraph.graph import MessagesState, END
from langchain.chat_models import init_chat_model
from langchain_classic.tools.retriever import create_retriever_tool
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Literal, List, Optional
import os
from app.core.config import settings
from app.workflows.prompt_loader import (
    get_system_message,
    get_prompt,
    get_retriever_tool_config,
    get_settings,
    get_hitl_settings,
    should_use_node_level_gate,
    should_review_documents
)
from langgraph.types import interrupt, Command

# Ensure OPENAI_API_KEY is set in environment
# Some langchain components check os.environ directly
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

# Load settings from prompts.json
_settings = get_settings()


class GradeDocuments(BaseModel):
    """Grade documents using a binary score for relevance check."""
    binary_score: str = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )


def create_workflow_nodes(
    retriever_tool: BaseTool,
    all_tools: Optional[List[BaseTool]] = None,
    model_name: str = None
):
    """Create workflow node functions with shared models.
    
    Args:
        retriever_tool: The retriever tool instance (used for document grading)
        all_tools: All available tools (retriever + custom tools)
        model_name: Model name (defaults to value from prompts.json)
    """
    # Default to just retriever tool if no tools list provided
    if all_tools is None:
        all_tools = [retriever_tool]
    # Use model from prompts.json if not specified
    if model_name is None:
        model_name = _settings.get('default_model', 'gpt-4o-mini')
    
    temperature = _settings.get('default_temperature', 0)
    streaming_enabled = _settings.get('streaming_enabled', True)
    
    # Initialize models with settings from prompts.json
    response_model = init_chat_model(
        model_name, 
        temperature=temperature, 
        streaming=streaming_enabled
    )
    grader_model = init_chat_model(model_name, temperature=temperature)
    
    def _get_latest_user_question(messages, exclude_last: bool = False):
        """Helper to find the most recent user message in the conversation.
        
        With checkpointing, messages[0] might be from a previous conversation turn.
        We need to find the actual current question being asked.
        
        Args:
            messages: List of messages from the state
            exclude_last: If True, exclude the last message (e.g., when it's a tool response)
        
        Returns:
            The content of the most recent user message
        """
        search_messages = messages[:-1] if exclude_last else messages
        
        for msg in reversed(search_messages):
            # Check for LangChain message objects
            if hasattr(msg, 'type') and msg.type == "human":
                return msg.content
            # Check for dict-style messages
            elif isinstance(msg, dict) and msg.get("role") == "user":
                return msg.get("content", "")
        
        # Fallback to first message if no user message found
        return messages[0].content if messages else ""
    
    def generate_query_or_respond(state: MessagesState):
        """Call the model to generate a response based on the current state.
        
        CRITICAL: In multi-turn conversations with checkpointing, we must ensure
        the LLM focuses on the LATEST user question, not previous ones in the thread.
        
        Also handles incomplete tool call sequences from corrupted checkpoints.
        """
        messages = state["messages"]
        
        # CRITICAL: Clean up ALL incomplete tool call sequences from corrupted checkpoints
        # OpenAI requires: AI message with tool_calls → MUST be followed by tool messages
        # Strategy: Skip any AI message with tool_calls that isn't immediately followed
        # by tool messages (or has tool messages but not for all tool_call_ids)
        
        cleaned_messages = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            msg_type = getattr(msg, 'type', None) or (msg.get('type') if isinstance(msg, dict) else None)
            msg_role = getattr(msg, 'role', None) or (msg.get('role') if isinstance(msg, dict) else None)
            
            # Check if this is an AI/assistant message
            is_ai = (msg_type == "ai") or (msg_role == "assistant")
            
            if is_ai:
                # Check if it has tool_calls
                tool_calls = None
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    tool_calls = msg.tool_calls
                elif isinstance(msg, dict) and msg.get('tool_calls'):
                    tool_calls = msg.get('tool_calls')
                
                if tool_calls:
                    # Extract ALL tool_call_ids from this AI message
                    tool_call_ids = set()
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            tc_id = tc.get('id')
                            if tc_id:
                                tool_call_ids.add(tc_id)
                        elif hasattr(tc, 'id'):
                            tool_call_ids.add(tc.id)
                    
                    # Safety check: If we couldn't extract tool_call_ids, skip to be safe
                    if not tool_call_ids:
                        # Can't verify - skip this message to prevent errors
                        i += 1
                        continue
                    
                    # Check if ALL tool_call_ids have corresponding tool responses
                    # Look ahead through remaining messages to find tool responses
                    found_responses = set()
                    for j in range(i + 1, len(messages)):
                        next_msg = messages[j]
                        next_type = getattr(next_msg, 'type', None) or (next_msg.get('type') if isinstance(next_msg, dict) else None)
                        next_role = getattr(next_msg, 'role', None) or (next_msg.get('role') if isinstance(next_msg, dict) else None)
                        
                        # Check if this is a tool message
                        is_tool = (next_type == "tool") or (next_role == "tool")
                        if is_tool:
                            # Extract tool_call_id
                            tool_call_id = None
                            if hasattr(next_msg, 'tool_call_id'):
                                tool_call_id = next_msg.tool_call_id
                            elif isinstance(next_msg, dict):
                                tool_call_id = next_msg.get('tool_call_id')
                            
                            if tool_call_id and tool_call_id in tool_call_ids:
                                found_responses.add(tool_call_id)
                        
                        # Stop looking if we hit another user message (new turn)
                        if (next_type == "human") or (next_role == "user"):
                            break
                    
                    # If we didn't find responses for ALL tool_call_ids, skip this incomplete AI message
                    if found_responses != tool_call_ids:
                        # Skip this incomplete AI message
                        i += 1
                        continue
            
            # Message is safe to include
            cleaned_messages.append(msg)
            i += 1
        
        # Get the latest user question - this is what we're answering NOW
        latest_question = _get_latest_user_question(cleaned_messages, exclude_last=False)
        
        # Build context with explicit focus on current question
        # Load system message from prompts.json
        system_msg = get_system_message(
            "generate_query_or_respond",
            current_question=latest_question
        )
        
        messages_with_context = [
            {"role": "system", "content": system_msg}
        ] + list(cleaned_messages)
        
        # Bind ALL tools to the model (not just retriever)
        response = (
            response_model
            .bind_tools(all_tools).invoke(messages_with_context)
        )
        return {"messages": [response]}
    
    def grade_documents(
        state: MessagesState,
    ) -> Literal["generate_answer", "rewrite_question"]:
        """Determine whether the retrieved documents are relevant to the question.
        
        CRITICAL: Prevents infinite loops by limiting rewrites to 1 attempt.
        After one rewrite, always generates answer even if docs aren't perfect.
        """
        messages = state["messages"]
        
        # CRITICAL: Prevent infinite loops by limiting rewrites to 1
        # Check recent messages (last 6) for rewrite pattern:
        # Pattern: user → ai (tool_call) → tool → user (rewritten) → ai (tool_call) → tool
        # If we see 2 tool responses in recent messages, we've already rewritten once
        
        recent_messages = messages[-6:] if len(messages) > 6 else messages
        tool_responses_in_recent = sum(
            1 for msg in recent_messages
            if (hasattr(msg, 'type') and msg.type == "tool") or
               (isinstance(msg, dict) and msg.get("type") == "tool") or
               (isinstance(msg, dict) and msg.get("name"))  # Tool messages have 'name' field
        )
        
        # If we have 2+ tool responses in recent messages, we've already rewritten once
        # Break the loop by going to generate_answer
        if tool_responses_in_recent >= 2:
            return "generate_answer"
        
        # Get the current question (exclude last message which should be the tool response)
        question = _get_latest_user_question(messages, exclude_last=True)
        
        # CRITICAL: Find the actual tool response message (not just assume it's last)
        # Tool responses come after AI messages with tool_calls
        context = ""
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            msg_type = getattr(msg, 'type', None) or (msg.get('type') if isinstance(msg, dict) else None)
            msg_role = getattr(msg, 'role', None) or (msg.get('role') if isinstance(msg, dict) else None)
            
            # Check if this is a tool message
            if (msg_type == "tool") or (msg_role == "tool"):
                # This is the tool response - extract content
                if hasattr(msg, 'content'):
                    context = msg.content
                elif isinstance(msg, dict):
                    context = msg.get('content', '')
                break
        
        # If no tool response found, try last message as fallback
        if not context and messages:
            last_msg = messages[-1]
            if hasattr(last_msg, 'content'):
                context = last_msg.content
            elif isinstance(last_msg, dict):
                context = last_msg.get('content', '')
        
        # Load prompt from prompts.json
        prompt = get_prompt("grade_documents", question=question, context=context)
        response = (
            grader_model
            .with_structured_output(GradeDocuments).invoke(
                [{"role": "user", "content": prompt}]
            )
        )
        score = response.binary_score
        
        if score == "yes":
            return "generate_answer"
        else:
            # First time grading as "no" - allow one rewrite
            return "rewrite_question"
    
    def rewrite_question(state: MessagesState):
        """Rewrite the original user question."""
        messages = state["messages"]
        
        # Get the current question
        question = _get_latest_user_question(messages, exclude_last=False)
        
        # Load prompt from prompts.json
        prompt = get_prompt("rewrite_question", question=question)
        response = response_model.invoke([{"role": "user", "content": prompt}])
        return {"messages": [{"role": "user", "content": response.content}]}
    
    def generate_answer(state: MessagesState):
        """Generate an answer from retrieved context."""
        messages = state["messages"]
        
        # Get the current question (exclude last message which should be the tool response)
        question = _get_latest_user_question(messages, exclude_last=True)
        
        # Helper to convert content to string (handles list content from some message types)
        def _content_to_string(raw_content):
            if raw_content is None:
                return ""
            if isinstance(raw_content, list):
                parts = []
                for item in raw_content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        parts.append(item.get('text', str(item)))
                    else:
                        parts.append(str(item))
                return "\n".join(parts)
            return str(raw_content) if not isinstance(raw_content, str) else raw_content
        
        # CRITICAL: Find the actual tool response message (not just assume it's last)
        # Tool responses come after AI messages with tool_calls
        context = ""
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            msg_type = getattr(msg, 'type', None) or (msg.get('type') if isinstance(msg, dict) else None)
            msg_role = getattr(msg, 'role', None) or (msg.get('role') if isinstance(msg, dict) else None)
            
            # Check if this is a tool message
            if (msg_type == "tool") or (msg_role == "tool"):
                # This is the tool response - extract content
                if hasattr(msg, 'content'):
                    context = _content_to_string(msg.content)
                elif isinstance(msg, dict):
                    context = _content_to_string(msg.get('content', ''))
                break
        
        # If no tool response found, try last message as fallback
        if not context and messages:
            last_msg = messages[-1]
            if hasattr(last_msg, 'content'):
                context = _content_to_string(last_msg.content)
            elif isinstance(last_msg, dict):
                context = _content_to_string(last_msg.get('content', ''))
        
        # Handle empty context case
        if not context or context.strip() == "":
            # No context retrieved - provide helpful response
            response_content = "I don't have enough information in the provided documents to answer this question. Please ensure relevant documents have been ingested."
            from langchain_core.messages import AIMessage
            return {"messages": [AIMessage(content=response_content)]}
        
        # Load prompt from prompts.json
        prompt = get_prompt("generate_answer", question=question, context=context)
        response = response_model.invoke([{"role": "user", "content": prompt}])
        return {"messages": [response]}
    
    def route_after_tools(
        state: MessagesState,
    ) -> Literal["generate_answer", "rewrite_question", END]:
        """Route after tool execution based on which tool was called.
        
        If retriever tool was called: grade documents and route accordingly
        If other tools were called: go directly to END (response already generated by tool)
        """
        messages = state["messages"]
        
        # Find the most recent tool response
        last_tool_name = None
        for msg in reversed(messages):
            msg_type = getattr(msg, 'type', None) or (msg.get('type') if isinstance(msg, dict) else None)
            msg_role = getattr(msg, 'role', None) or (msg.get('role') if isinstance(msg, dict) else None)
            
            if (msg_type == "tool") or (msg_role == "tool"):
                # Get the tool name
                if hasattr(msg, 'name'):
                    last_tool_name = msg.name
                elif isinstance(msg, dict):
                    last_tool_name = msg.get('name')
                break
        
        # If retriever tool was called, grade the documents
        retriever_name = retriever_tool.name
        if last_tool_name == retriever_name:
            # Use existing grade_documents logic
            return grade_documents(state)
        
        # For other tools, the tool result becomes context for the answer
        # Go to generate_answer to formulate a natural response
        return "generate_answer"
    
    return {
        "generate_query_or_respond": generate_query_or_respond,
        "grade_documents": grade_documents,
        "route_after_tools": route_after_tools,
        "rewrite_question": rewrite_question,
        "generate_answer": generate_answer,
    }


# List of sensitive tools that require human approval at node level
SENSITIVE_TOOLS = [
    "apply_for_leave",
    "approve_leave_for_employee",
    "cancel_leave_for_employee",
    "apply_attendance",
    "approve_attendance_for_employee",
    "cancel_attendance_for_employee",
    "apply_leave_for_employee",
]


def create_human_approval_node(sensitive_tools: list = None):
    """Create a node that requires human approval for sensitive tool calls.
    
    This implements Pattern 2: Node-Level Gate for Sensitive Tools.
    When the LLM decides to call a sensitive tool, this node intercepts
    the call and requires human approval before proceeding.
    
    Args:
        sensitive_tools: List of tool names requiring approval.
                        Defaults to SENSITIVE_TOOLS if not provided.
    
    Returns:
        A function that can be used as a LangGraph node.
    """
    if sensitive_tools is None:
        sensitive_tools = SENSITIVE_TOOLS
    
    def human_approval_node(state: MessagesState) -> Command[Literal["tools", "generate_query_or_respond"]]:
        """Gate node that requires human approval for sensitive tool calls."""
        messages = state["messages"]
        
        # Check if node-level gate is enabled
        if not should_use_node_level_gate():
            # Skip approval, proceed to tools
            return Command(goto="tools")
        
        # Get the last message (should be AI message with tool_calls)
        if not messages:
            return Command(goto="tools")
        
        last_message = messages[-1]
        
        # Check if there are pending tool calls
        tool_calls = None
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            tool_calls = last_message.tool_calls
        elif isinstance(last_message, dict) and last_message.get('tool_calls'):
            tool_calls = last_message.get('tool_calls')
        
        if not tool_calls:
            return Command(goto="tools")  # No tool calls, proceed
        
        # Check if any tool call is sensitive
        pending_sensitive_tools = []
        for tool_call in tool_calls:
            tool_name = None
            tool_args = {}
            
            if isinstance(tool_call, dict):
                tool_name = tool_call.get('name')
                tool_args = tool_call.get('args', {})
            elif hasattr(tool_call, 'name'):
                tool_name = tool_call.name
                tool_args = getattr(tool_call, 'args', {})
            
            if tool_name and tool_name in sensitive_tools:
                pending_sensitive_tools.append({
                    "tool": tool_name,
                    "args": tool_args
                })
        
        if not pending_sensitive_tools:
            return Command(goto="tools")  # No sensitive tools, proceed
        
        # INTERRUPT: Request human approval
        decision = interrupt({
            "action": "tool_approval",
            "message": "The agent wants to perform the following actions. Do you approve?",
            "pending_actions": pending_sensitive_tools,
            "options": ["approve", "reject"]
        })
        
        if not decision.get("approved", False) and decision.get("action") != "approve":
            # Rejected - tell the model to suggest alternatives
            from langchain_core.messages import HumanMessage
            return Command(
                goto="generate_query_or_respond",
                update={"messages": [HumanMessage(content="Please don't perform that action. Suggest alternatives instead.")]}
            )
        
        # Approved - proceed to tools
        return Command(goto="tools")
    
    return human_approval_node


def create_document_review_node():
    """Create a node that lets humans review retrieved documents before generating an answer.
    
    This implements Pattern 4: Node-Level Document Review.
    After documents are retrieved but before answer generation, users can
    review the documents and choose to use all, add context, or reject all.
    
    Returns:
        A function that can be used as a LangGraph node.
    """
    def document_review_node(state: MessagesState):
        """Review node that allows human review of retrieved documents."""
        messages = state["messages"]
        
        # Check if document review is enabled
        if not should_review_documents():
            return {"messages": messages}  # Skip review, proceed as-is
        
        # Find the retriever tool response
        context = ""
        for msg in reversed(messages):
            msg_type = getattr(msg, 'type', None) or (msg.get('type') if isinstance(msg, dict) else None)
            msg_name = getattr(msg, 'name', None) or (msg.get('name') if isinstance(msg, dict) else None)
            
            if msg_type == "tool" and msg_name == "retrieve_documents":
                if hasattr(msg, 'content'):
                    context = msg.content
                elif isinstance(msg, dict):
                    context = msg.get('content', '')
                break
        
        if not context or len(context.strip()) < 50:
            # No meaningful documents, skip review
            return {"messages": messages}
        
        # INTERRUPT: Let human review documents
        review_result = interrupt({
            "action": "document_review",
            "message": "Review retrieved documents before generating answer:",
            "documents": context[:2000],  # Truncate for display
            "document_count": context.count("---") + 1,  # Rough count
            "options": ["use_all", "add_context", "reject_all"]
        })
        
        action = review_result.get("action", "use_all")
        
        if action == "reject_all":
            # Force a rewrite
            from langchain_core.messages import HumanMessage
            return Command(
                goto="rewrite_question",
                update={"messages": [HumanMessage(content="The retrieved documents are not relevant. Please reformulate the search.")]}
            )
        
        if action == "add_context":
            additional = review_result.get("additional_context", "")
            if additional:
                # Append user's context to the tool response
                from langchain_core.messages import ToolMessage
                enhanced_context = f"{context}\n\n--- User-provided context ---\n{additional}"
                # Update the last tool message
                updated_messages = []
                for msg in messages:
                    msg_type = getattr(msg, 'type', None) or (msg.get('type') if isinstance(msg, dict) else None)
                    msg_name = getattr(msg, 'name', None) or (msg.get('name') if isinstance(msg, dict) else None)
                    
                    if msg_type == "tool" and msg_name == "retrieve_documents":
                        tool_call_id = getattr(msg, 'tool_call_id', None) or (msg.get('tool_call_id') if isinstance(msg, dict) else None)
                        updated_messages.append(ToolMessage(content=enhanced_context, name="retrieve_documents", tool_call_id=tool_call_id))
                    else:
                        updated_messages.append(msg)
                return {"messages": updated_messages}
        
        # use_all - proceed with original documents
        return {"messages": messages}
    
    return document_review_node

