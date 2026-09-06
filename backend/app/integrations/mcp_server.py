"""Model Context Protocol (MCP) Server for EchoDrive.

Implements standard MCP Tool definitions and SSE transport handlers, allowing
both Agora's `mcp_client_python` TEN extension and internal voice pipeline components
to execute partial RAG and deterministic catalog queries.
"""

import asyncio
import json
import uuid
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from pydantic import BaseModel, Field

from .knowledge_retrieval import knowledge_engine, KnowledgeChunk
from ..catalog.catalog_service import catalog_service

logger = logging.getLogger(__name__)


class MCPToolParameter(BaseModel):
    name: str
    type: str = "string"
    description: str
    required: bool = True
    items: Optional[Dict[str, str]] = None


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    parameters: List[MCPToolParameter] = Field(default_factory=list)
    input_schema: Dict[str, Any] = Field(default_factory=dict)


class DealershipMCPServer:
    """Dealership MCP Server handling Tool registration, execution, and SSE communication."""

    def __init__(self) -> None:
        self.tools: Dict[str, MCPToolDefinition] = {}
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {}
        self._active_sessions: Dict[str, asyncio.Queue] = {}
        self._register_default_tools()

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: List[MCPToolParameter],
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> None:
        """Register a new MCP tool with its parameter schema and async handler."""
        props = {}
        required_list = []
        for param in parameters:
            prop_def: Dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.type == "array" and param.items:
                prop_def["items"] = param.items
            props[param.name] = prop_def
            if param.required:
                required_list.append(param.name)

        input_schema = {
            "type": "object",
            "properties": props,
            "required": required_list,
        }

        tool_def = MCPToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            input_schema=input_schema,
        )
        self.tools[name] = tool_def
        self._handlers[name] = handler
        logger.info(f"Registered MCP tool: '{name}'")

    def _register_default_tools(self) -> None:
        """Registers default authoritative Dealership RAG and Catalog tools."""

        # 1. query_dealership_knowledge (Partial RAG)
        self.register_tool(
            name="query_dealership_knowledge",
            description=(
                "Query authoritative dealership policies, 7-day return guarantee, warranty details, "
                "financing rates, test drive rules, EV charging, and service packages."
            ),
            parameters=[
                MCPToolParameter(
                    name="query",
                    type="string",
                    description="The search query or customer question regarding dealership policy or specifications",
                    required=True,
                ),
                MCPToolParameter(
                    name="category",
                    type="string",
                    description="Optional filter category: 'policy', 'warranty', 'financing', 'test_drive', 'ev_charging', 'service'",
                    required=False,
                ),
            ],
            handler=self._handle_query_knowledge,
        )

        # 2. get_dealership_policy
        self.register_tool(
            name="get_dealership_policy",
            description="Retrieve exact policy rules by topic name (e.g. 'return_policy', 'warranty', 'financing', 'trade_in').",
            parameters=[
                MCPToolParameter(
                    name="topic",
                    type="string",
                    description="Policy topic: return_policy, warranty, financing, test_drive, trade_in, ev_charging",
                    required=True,
                )
            ],
            handler=self._handle_get_policy,
        )

        # 3. search_vehicle_catalog (Deterministic Tool)
        self.register_tool(
            name="search_vehicle_catalog",
            description="Search dealership live inventory by brand, body type, fuel type, or budget.",
            parameters=[
                MCPToolParameter(
                    name="make",
                    type="string",
                    description="Vehicle brand (e.g. Mercedes-Benz, BMW, Audi, Mahindra, Tata)",
                    required=False,
                ),
                MCPToolParameter(
                    name="body_type",
                    type="string",
                    description="Body type: 'sedan', 'suv', 'coupe'",
                    required=False,
                ),
                MCPToolParameter(
                    name="fuel_type",
                    type="string",
                    description="Fuel type: 'petrol', 'diesel', 'electric'",
                    required=False,
                ),
                MCPToolParameter(
                    name="max_budget_inr",
                    type="integer",
                    description="Maximum ex-showroom budget in INR",
                    required=False,
                ),
            ],
            handler=self._handle_search_catalog,
        )

    async def _handle_query_knowledge(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query_text = args.get("query", "")
        category = args.get("category")
        results = await knowledge_engine.query(query=query_text, category=category, top_k=2)
        return {
            "status": "success",
            "matched_count": len(results),
            "results": [
                {
                    "title": r.title,
                    "category": r.category,
                    "content": r.content,
                }
                for r in results
            ],
            "formatted_context": knowledge_engine.format_retrieval_prompt(results),
        }

    async def _handle_get_policy(self, args: Dict[str, Any]) -> Dict[str, Any]:
        topic = args.get("topic", "").lower()
        results = await knowledge_engine.query(query=topic, top_k=1)
        if results:
            match = results[0]
            return {
                "status": "success",
                "topic": topic,
                "title": match.title,
                "policy": match.content,
            }
        return {
            "status": "not_found",
            "message": f"No specific policy document found matching topic: '{topic}'",
        }

    async def _handle_search_catalog(self, args: Dict[str, Any]) -> Dict[str, Any]:
        make = args.get("make")
        body_type_str = args.get("body_type")
        fuel_type_str = args.get("fuel_type")
        max_budget = args.get("max_budget_inr")

        from ..catalog.models import BodyType, FuelType
        b_type = None
        if body_type_str:
            for bt in BodyType:
                if bt.value.lower() == body_type_str.lower() or bt.name.lower() == body_type_str.lower():
                    b_type = bt
                    break

        f_type = None
        if fuel_type_str:
            for ft in FuelType:
                if ft.value.lower() == fuel_type_str.lower() or ft.name.lower() == fuel_type_str.lower():
                    f_type = ft
                    break

        search_res = catalog_service.search(
            make=make,
            body_type=b_type,
            fuel_type=f_type,
            max_budget_inr=max_budget,
            limit=3,
        )
        return {
            "status": "success",
            "total_matched": search_res.total_matched,
            "vehicles": [
                {
                    "make": v.make,
                    "model": v.model,
                    "variant": v.variant,
                    "ex_showroom_price_inr": v.ex_showroom_price_inr,
                    "formatted_price": v.formatted_price_display,
                    "in_stock_units": v.in_stock_units,
                    "features": v.key_features[:3],
                }
                for v in search_res.vehicles
            ],
            "rag_context": catalog_service.format_rag_context(search_res.vehicles),
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns JSON schema of tools formatted for MCP specification / Agora extension."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in self.tools.values()
        ]

    async def call_tool(self, name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Direct async execution of an MCP tool."""
        handler = self._handlers.get(name)
        if not handler:
            return {
                "error": f"Tool '{name}' is not registered on this MCP server.",
                "is_error": True,
            }

        try:
            res = await handler(args or {})
            return res
        except Exception as e:
            logger.error(f"Error executing MCP tool '{name}': {e}", exc_info=True)
            return {
                "error": str(e),
                "is_error": True,
            }

    async def handle_json_rpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handles standard JSON-RPC 2.0 requests from MCP clients."""
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "echodrive-dealership-mcp",
                        "version": "1.0.0",
                    },
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.list_tools(),
                },
            }

        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            call_result = await self.call_tool(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(call_result, indent=2),
                        }
                    ],
                    "isError": call_result.get("is_error", False),
                },
            }

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }


# Singleton MCP server instance
mcp_server = DealershipMCPServer()
