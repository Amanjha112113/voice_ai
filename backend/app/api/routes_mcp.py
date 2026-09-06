"""FastAPI Routes for MCP (Model Context Protocol) SSE Transport.

Exposes SSE endpoints conforming to the MCP HTTP/SSE transport spec:
- GET /mcp/sse: Opens SSE stream, sends initial 'endpoint' event with URL for messages
- POST /mcp/messages: Receives JSON-RPC 2.0 requests from MCP clients (e.g. Agora TEN extension)
- GET /mcp/tools: Lightweight JSON endpoint to inspect registered tools
"""

import asyncio
import json
import uuid
import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import StreamingResponse

from ..integrations.mcp_server import mcp_server

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP Tools & Partial RAG"])

# Active SSE connection queues: session_id -> asyncio.Queue
_active_sessions: Dict[str, asyncio.Queue] = {}


@router.get("/tools")
async def list_mcp_tools():
    """Returns list of registered MCP tools and their JSON schemas."""
    return {"tools": mcp_server.list_tools()}


@router.post("/execute")
async def execute_tool_direct(request: Dict[str, Any]):
    """Direct REST execution of an MCP tool for debugging/control plane."""
    name = request.get("name")
    args = request.get("arguments", {})
    if not name:
        raise HTTPException(status_code=400, detail="Missing tool 'name'")
    result = await mcp_server.call_tool(name, args)
    return result


@router.get("/sse")
async def mcp_sse_endpoint(request: Request):
    """MCP SSE endpoint for connecting clients like Agora TEN mcp_client_python."""
    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _active_sessions[session_id] = queue

    # URL where client should send JSON-RPC POST requests
    base_url = str(request.base_url).rstrip("/")
    message_endpoint_url = f"{base_url}/mcp/messages?session_id={session_id}"

    async def event_generator():
        try:
            # 1. Send standard MCP endpoint event on initial connection
            yield f"event: endpoint\ndata: {message_endpoint_url}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    # Ping / Keepalive frame
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _active_sessions.pop(session_id, None)
            logger.info(f"MCP SSE connection closed for session={session_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/messages")
async def mcp_messages_endpoint(request: Request, session_id: str = Query(...)):
    """Receives JSON-RPC messages from MCP clients and queues response on SSE."""
    body = await request.json()
    logger.debug(f"MCP Message received for session {session_id}: {body.get('method')}")

    response = await mcp_server.handle_json_rpc(body)

    # Deliver response to client queue if active
    queue = _active_sessions.get(session_id)
    if queue:
        await queue.put(response)
        return {"status": "queued"}
    else:
        # Fallback return direct JSON-RPC response
        return response
