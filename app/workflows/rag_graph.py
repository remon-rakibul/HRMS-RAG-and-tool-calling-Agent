"""LangGraph workflow builder."""
from typing import List, Optional
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_classic.tools.retriever import create_retriever_tool
from langchain_core.tools import BaseTool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from app.workflows.nodes import create_workflow_nodes
from app.workflows.prompt_loader import get_retriever_tool_config
from app.workflows.tools import get_all_tools
from app.core.config import settings
from app.utils.db_uri import normalize_db_uri_for_asyncpg
from mcp_server.adapter import get_mcp_tools


def build_rag_graph(
    retriever,
    checkpointer,
    tool_name: str = None,
    tool_description: str = None,
    additional_tools: Optional[List[BaseTool]] = None
):
    """Build a LangGraph RAG workflow with the given retriever and checkpointer.
    
    Args:
        retriever: LangChain retriever instance
        checkpointer: PostgresSaver checkpointer instance
        tool_name: Name for the retriever tool (defaults to prompts.json)
        tool_description: Description for the retriever tool (defaults to prompts.json)
        additional_tools: Extra tools to add beyond the retriever and registered tools
    
    Returns:
        Compiled LangGraph workflow with checkpointer
    """
    # Load tool config from prompts.json if not provided
    tool_config = get_retriever_tool_config()
    if tool_name is None:
        tool_name = tool_config.get('name', 'retrieve_documents')
    if tool_description is None:
        tool_description = tool_config.get('description', 'Search and return information from ingested documents.')
    
    # Create retriever tool
    retriever_tool = create_retriever_tool(
        retriever,
        tool_name,
        tool_description,
    )
    
    # Get all tools: retriever + registered tools + additional tools
    all_tools = get_all_tools(retriever_tool)
    if additional_tools:
        for t in additional_tools:
            if t not in all_tools:
                all_tools.append(t)
    
    # Note: MCP tools should be loaded asynchronously and passed via additional_tools
    # This is handled in chat_service.py
    
    # Create workflow nodes with all tools
    nodes = create_workflow_nodes(retriever_tool, all_tools=all_tools)
    
    # Build workflow graph
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("generate_query_or_respond", nodes["generate_query_or_respond"])
    workflow.add_node("tools", ToolNode(all_tools))  # ToolNode handles ALL tools
    workflow.add_node("rewrite_question", nodes["rewrite_question"])
    workflow.add_node("generate_answer", nodes["generate_answer"])
    
    # Add edges
    workflow.add_edge(START, "generate_query_or_respond")
    
    # Conditional edge: decide whether to use tools
    workflow.add_conditional_edges(
        "generate_query_or_respond",
        tools_condition,
        {
            "tools": "tools",  # Route to unified tools node
            END: END,
        },
    )
    
    # After tools: route based on which tool was called
    # If retriever was used, grade documents; otherwise go to generate_answer
    workflow.add_conditional_edges(
        "tools",
        nodes["route_after_tools"],
    )
    
    workflow.add_edge("generate_answer", END)
    workflow.add_edge("rewrite_question", "generate_query_or_respond")
    
    # Compile workflow WITH checkpointer (required for checkpointing to work)
    graph = workflow.compile(checkpointer=checkpointer)
    
    return graph


async def get_checkpointer():
    """Get AsyncPostgresSaver checkpointer instance for true async support.
    
    Returns an AsyncPostgresSaver that works with astream_events for token-level streaming.
    """
    # Normalize DB URI - remove sslmode and convert to proper format
    normalized_db_uri = normalize_db_uri_for_asyncpg(settings.DATABASE_URL)
    
    # Convert to plain postgresql:// for psycopg (AsyncPostgresSaver uses psycopg3)
    db_uri = normalized_db_uri.replace("postgresql+asyncpg://", "postgresql://")
    
    # Create async connection pool
    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
    }
    
    pool = AsyncConnectionPool(
        conninfo=db_uri,
        max_size=20,
        kwargs=connection_kwargs
    )
    
    # Create AsyncPostgresSaver with the pool
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    
    return checkpointer

