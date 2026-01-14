"""API v1 router aggregator."""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, digest, remove, docs, chat, history, memory, agent, mcp

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(digest.router)
api_router.include_router(remove.router)
api_router.include_router(docs.router)
api_router.include_router(chat.router)
api_router.include_router(history.router)
api_router.include_router(memory.router)
api_router.include_router(agent.router)
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])

