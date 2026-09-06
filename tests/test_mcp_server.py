"""Unit tests for DealershipMCPServer and MCP Tool Handlers."""

import pytest
import json
from backend.app.integrations.mcp_server import DealershipMCPServer


@pytest.fixture
def server():
    return DealershipMCPServer()


def test_mcp_tool_listing_format(server):
    tools = server.list_tools()
    assert len(tools) >= 3
    tool_names = [t["name"] for t in tools]
    assert "query_dealership_knowledge" in tool_names
    assert "get_dealership_policy" in tool_names
    assert "search_vehicle_catalog" in tool_names

    # Verify JSON Schema specification compatibility
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"
        assert "properties" in tool["inputSchema"]


@pytest.mark.asyncio
async def test_mcp_call_query_dealership_knowledge(server):
    res = await server.call_tool(
        "query_dealership_knowledge",
        {"query": "what is your return and exchange policy?", "category": "policy"},
    )
    assert res.get("status") == "success"
    assert res.get("matched_count", 0) > 0
    assert "formatted_context" in res
    assert "7-Day" in res["results"][0]["title"]


@pytest.mark.asyncio
async def test_mcp_call_get_dealership_policy(server):
    res = await server.call_tool("get_dealership_policy", {"topic": "warranty"})
    assert res.get("status") == "success"
    assert "Comprehensive Warranty" in res.get("title", "")
    assert "3-year" in res.get("policy", "")


@pytest.mark.asyncio
async def test_mcp_call_search_vehicle_catalog(server):
    res = await server.call_tool(
        "search_vehicle_catalog",
        {"make": "Mercedes-Benz", "body_type": "sedan"},
    )
    assert res.get("status") == "success"
    assert res.get("total_matched", 0) > 0
    assert len(res.get("vehicles", [])) > 0
    assert res["vehicles"][0]["make"] == "Mercedes-Benz"


@pytest.mark.asyncio
async def test_mcp_json_rpc_initialize_and_tools_list(server):
    # Test JSON-RPC initialize
    init_req = {
        "jsonrpc": "2.0",
        "id": "req-1",
        "method": "initialize",
        "params": {},
    }
    init_res = await server.handle_json_rpc(init_req)
    assert init_res["id"] == "req-1"
    assert "serverInfo" in init_res["result"]
    assert init_res["result"]["serverInfo"]["name"] == "echodrive-dealership-mcp"

    # Test JSON-RPC tools/list
    list_req = {
        "jsonrpc": "2.0",
        "id": "req-2",
        "method": "tools/list",
        "params": {},
    }
    list_res = await server.handle_json_rpc(list_req)
    assert list_res["id"] == "req-2"
    assert len(list_res["result"]["tools"]) >= 3


@pytest.mark.asyncio
async def test_mcp_json_rpc_tools_call(server):
    call_req = {
        "jsonrpc": "2.0",
        "id": "req-3",
        "method": "tools/call",
        "params": {
            "name": "query_dealership_knowledge",
            "arguments": {"query": "warranty details"},
        },
    }
    call_res = await server.handle_json_rpc(call_req)
    assert call_res["id"] == "req-3"
    assert "content" in call_res["result"]
    content_text = call_res["result"]["content"][0]["text"]
    parsed_payload = json.loads(content_text)
    assert parsed_payload["status"] == "success"
    assert parsed_payload["matched_count"] > 0
