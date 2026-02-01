"""Chat service for RAG workflow orchestration."""
from typing import AsyncGenerator, Optional
import uuid
from langchain_core.messages import convert_to_messages
from app.services.vector_store_service import get_vector_store_service
from app.workflows.rag_graph import build_rag_graph, get_checkpointer
from app.utils.retrieval_logger import get_retrieval_logger
from mcp_server.adapter import get_mcp_tools
from app.core.config import settings

# Debug flag - set to True to see streaming events in console
DEBUG_STREAMING = False


class ChatService:
    """Service for managing chat interactions with RAG workflow."""
    
    def __init__(self):
        self.vector_store_service = get_vector_store_service()
    
    async def get_graph_for_user(self, user_id: Optional[int] = None, checkpointer=None, mcp_tools=None):
        """Get a RAG graph configured for a specific user with checkpointer.
        
        Creates a RAG workflow that retrieves only from the user's documents.
        
        Args:
            user_id: User ID for scoping retriever (filters documents by user)
            checkpointer: PostgresSaver checkpointer instance (required)
            mcp_tools: Optional list of MCP tools (if None, will be loaded automatically)
            
        Returns:
            Compiled LangGraph workflow with user-isolated retrieval
        """
        # Get user-scoped retriever with top-k=5 filtering
        # This will:
        # 1. Filter documents WHERE user_id = {user_id}
        # 2. Rank filtered docs by cosine similarity to query
        # 3. Return top 5 most relevant documents from user's collection
        retriever = self.vector_store_service.get_retriever(
            user_id=user_id,
            search_type="similarity",  # Cosine similarity search
            search_kwargs={"k": 5}      # Retrieve top 5 most similar docs
        )
        
        # Load MCP tools only if USE_NATIVE_TOOLS is False
        additional_tools = None
        if not settings.USE_NATIVE_TOOLS:
            if mcp_tools is None:
                mcp_tools = await get_mcp_tools()
            additional_tools = mcp_tools if mcp_tools else None
        
        # Build graph with user's retriever AND checkpointer
        graph = build_rag_graph(
            retriever=retriever,
            checkpointer=checkpointer,
            tool_name="retrieve_documents",
            tool_description="Search and return information from your ingested documents.",
            additional_tools=additional_tools
        )
        
        return graph
    
    async def stream_chat(
        self,
        message: str,
        user_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        employee_id: Optional[int] = None
    ) -> AsyncGenerator[dict, None]:
        """Stream chat response from RAG workflow with token-by-token streaming.
        
        Args:
            message: User's chat message
            user_id: FastAPI user ID for document scoping
            thread_id: Conversation thread ID
            employee_id: HRMS employee ID for leave applications and other HR operations
        
        Yields:
            Dict with keys: type ('token', 'done', 'error'), content, thread_id
        """
        try:
            # Set employee_id in context for tools to access
            from app.workflows.context import set_employee_id, clear_context
            
            if employee_id:
                set_employee_id(employee_id)
                print(f"[ChatService] Employee context set: employee_id={employee_id}", flush=True)
            else:
                clear_context()
                print(f"[ChatService] No employee_id provided", flush=True)
            
            # Prepare config with thread_id
            if thread_id is None:
                thread_id = str(uuid.uuid4())
            
            # Get AsyncPostgresSaver for true async streaming support
            checkpointer = await get_checkpointer()
            
            # Build graph WITH checkpointer
            graph = await self.get_graph_for_user(user_id=user_id, checkpointer=checkpointer)
            
            # Prepare input
            input_messages = convert_to_messages([{"role": "user", "content": message}])
            
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 50  # Prevent infinite loops (default is 25)
            }
            
            # Set context for retrieval logging
            logger = get_retrieval_logger()
            logger.set_context(thread_id=thread_id, original_question=message)
            
            # Track streaming state
            full_content = ""
            is_using_tools = False  # True when tools node is active
            
            async for event in graph.astream_events(
                {"messages": input_messages},
                config=config,
                version="v1"
            ):
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node", "")
                event_type = event.get("event", "")
                
                # DEBUG logging
                if DEBUG_STREAMING and event_type in ["on_chain_start", "on_chain_end", "on_chat_model_stream"]:
                    print(f"[DEBUG] {event_type} | node='{node_name}'", flush=True)
                
                # Track when tools node starts (means LLM decided to use a tool)
                if event_type == "on_chain_start" and node_name == "tools":
                    is_using_tools = True
                
                # Track when tools node ends
                if event_type == "on_chain_end" and node_name == "tools":
                    is_using_tools = False
                
                # Detect interrupts from HITL (Human-in-the-Loop) patterns
                if event_type == "on_chain_end":
                    data = event.get("data", {})
                    output = data.get("output", {})
                    
                    # Check if this event contains an interrupt
                    if isinstance(output, dict) and "__interrupt__" in output:
                        interrupt_list = output["__interrupt__"]
                        if interrupt_list and len(interrupt_list) > 0:
                            interrupt_value = interrupt_list[0]
                            # Handle Interrupt object (has .value attribute)
                            if hasattr(interrupt_value, 'value'):
                                interrupt_data = interrupt_value.value
                            else:
                                interrupt_data = interrupt_value
                            
                            print(f"[ChatService] Interrupt detected: {interrupt_data.get('action', 'unknown')}", flush=True)
                            
                            yield {
                                "type": "interrupt",
                                "interrupt_data": interrupt_data,
                                "thread_id": thread_id
                            }
                            return  # Stop streaming, wait for resume
                
                # Stream tokens from LLM
                if event_type == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        
                        # Stream from generate_query_or_respond (direct response, no tool call)
                        # Only stream if we're NOT in the middle of using tools
                        if node_name == "generate_query_or_respond" and not is_using_tools:
                            full_content += content
                            yield {
                                "type": "token",
                                "content": content,
                                "thread_id": thread_id
                            }
                        
                        # Stream from generate_answer (after tool/retrieval)
                        elif node_name == "generate_answer":
                            full_content += content
                            yield {
                                "type": "token",
                                "content": content,
                                "thread_id": thread_id
                            }
            
            # Yield completion
            yield {
                "type": "done",
                "content": full_content,
                "thread_id": thread_id
            }
            
        except Exception as e:
            import traceback
            error_str = str(e)
            
            # Check for incomplete tool call sequence error
            if "tool_calls" in error_str and "tool_call_id" in error_str:
                error_detail = (
                    f"Checkpoint contains incomplete tool call sequence. "
                    f"This usually happens when a conversation was interrupted.\n\n"
                    f"SOLUTION: Use a new thread_id (leave empty or generate a new UUID) "
                    f"or clear the checkpoint for thread_id: {thread_id}\n\n"
                    f"Original error: {error_str}\n{traceback.format_exc()}"
                )
            else:
                error_detail = f"{error_str}\n{traceback.format_exc()}"
            
            yield {
                "type": "error",
                "content": error_detail,
                "thread_id": thread_id if 'thread_id' in locals() else None
            }
        finally:
            # Always clear context after execution
            from app.workflows.context import clear_context
            clear_context()
    
    async def stream_resume(
        self,
        thread_id: str,
        resume_data: dict,
        user_id: Optional[int] = None,
        employee_id: Optional[int] = None
    ) -> AsyncGenerator[dict, None]:
        """Resume an interrupted graph execution with user's response.
        
        Args:
            thread_id: Thread ID of the interrupted conversation
            resume_data: User's response to the interrupt (e.g., {'action': 'approve', 'remarks': '...'})
            user_id: FastAPI user ID for document scoping
            employee_id: HRMS employee ID for HR operations
        
        Yields:
            Dict with keys: type ('token', 'done', 'error', 'interrupt'), content, thread_id, interrupt_data
        """
        try:
            from langgraph.types import Command
            from app.workflows.context import set_employee_id, clear_context
            
            # Set employee context
            if employee_id:
                set_employee_id(employee_id)
                print(f"[ChatService] Resume: Employee context set: employee_id={employee_id}", flush=True)
            else:
                clear_context()
            
            # Get checkpointer and build graph
            checkpointer = await get_checkpointer()
            graph = await self.get_graph_for_user(user_id=user_id, checkpointer=checkpointer)
            
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 50
            }
            
            # Track streaming state
            full_content = ""
            is_using_tools = False
            
            print(f"[ChatService] Resuming thread {thread_id} with data: {resume_data}", flush=True)
            
            async for event in graph.astream_events(
                Command(resume=resume_data),
                config=config,
                version="v1"
            ):
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node", "")
                event_type = event.get("event", "")
                data = event.get("data", {})
                
                # DEBUG logging - log all events to help debug
                if DEBUG_STREAMING:
                    print(f"[DEBUG Resume] {event_type} | node='{node_name}' | keys={list(data.keys())}", flush=True)
                
                # Track when tools node starts
                if event_type == "on_chain_start" and node_name == "tools":
                    is_using_tools = True
                
                # Track when tools node ends
                if event_type == "on_chain_end" and node_name == "tools":
                    is_using_tools = False
                
                # Detect nested interrupts (multi-step approval flows)
                # Check multiple event types and locations where interrupt might appear
                if event_type in ["on_chain_end", "on_tool_end"]:
                    output = data.get("output", {})
                    
                    # Check output for __interrupt__
                    if isinstance(output, dict) and "__interrupt__" in output:
                        interrupt_list = output["__interrupt__"]
                        if interrupt_list and len(interrupt_list) > 0:
                            interrupt_value = interrupt_list[0]
                            if hasattr(interrupt_value, 'value'):
                                interrupt_data = interrupt_value.value
                            else:
                                interrupt_data = interrupt_value
                            
                            print(f"[ChatService] Nested interrupt detected in {event_type}: {interrupt_data.get('action', 'unknown')}", flush=True)
                            
                            yield {
                                "type": "interrupt",
                                "interrupt_data": interrupt_data,
                                "thread_id": thread_id
                            }
                            return  # Stop streaming, wait for next resume
                    
                    # Also check if data itself has __interrupt__ (different event structures)
                    if isinstance(data, dict) and "__interrupt__" in data:
                        interrupt_list = data["__interrupt__"]
                        if interrupt_list and len(interrupt_list) > 0:
                            interrupt_value = interrupt_list[0]
                            if hasattr(interrupt_value, 'value'):
                                interrupt_data = interrupt_value.value
                            else:
                                interrupt_data = interrupt_value
                            
                            print(f"[ChatService] Nested interrupt detected in data: {interrupt_data.get('action', 'unknown')}", flush=True)
                            
                            yield {
                                "type": "interrupt",
                                "interrupt_data": interrupt_data,
                                "thread_id": thread_id
                            }
                            return
                
                # Stream tokens from LLM
                if event_type == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        
                        # Stream from generate_query_or_respond (direct response)
                        if node_name == "generate_query_or_respond" and not is_using_tools:
                            full_content += content
                            yield {
                                "type": "token",
                                "content": content,
                                "thread_id": thread_id
                            }
                        
                        # Stream from generate_answer (after tool/retrieval)
                        elif node_name == "generate_answer":
                            full_content += content
                            yield {
                                "type": "token",
                                "content": content,
                                "thread_id": thread_id
                            }
            
            # Yield completion
            yield {
                "type": "done",
                "content": full_content,
                "thread_id": thread_id
            }
            
        except Exception as e:
            import traceback
            error_str = str(e)
            error_detail = f"{error_str}\n{traceback.format_exc()}"
            
            print(f"[ChatService] Resume error: {error_str}", flush=True)
            
            yield {
                "type": "error",
                "content": error_detail,
                "thread_id": thread_id
            }
        finally:
            from app.workflows.context import clear_context
            clear_context()


def get_chat_service() -> ChatService:
    """Get chat service instance."""
    return ChatService()

