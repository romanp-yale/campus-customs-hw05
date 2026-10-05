"""Shop access exclusively through MCP; no SQLite or database imports."""

import json
import os
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from .config import ROOT

AGENT_TOOLS = frozenset({
    "get_ticket_101_tee_order_context", "get_ticket_102_rent_context",
    "get_ticket_103_hoodie_discount_context", "read_shop_board", "request_payment",
    "save_board_draft", "draft_purchase_order",
    "record_discount_decision", "fulfill_ticket_order", "close_paid_rent_ticket",
    "decline_ticket_request",
})


class ShopMCP:
    def __init__(self, human: bool = False):
        config = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["campus_customs"]
        # Keys never enter agent tool arguments or the normal shop process.
        env = {k:v for k,v in os.environ.items() if k not in ("PORTKEY_API_KEY", "CAMPUS_HUMAN_APPROVAL_KEY")}
        if human:
            key = os.getenv("CAMPUS_HUMAN_APPROVAL_KEY", "")
            if not key:
                raise RuntimeError("Configure CAMPUS_HUMAN_APPROVAL_KEY for human approval commands.")
            env["CAMPUS_HUMAN_APPROVAL_KEY"] = key
        self.human = human
        cwd = Path(config.get("cwd", "."))
        cwd = cwd if cwd.is_absolute() else (ROOT / cwd).resolve()
        command = sys.executable if config["command"] == "python" else config["command"]
        self.client = Client(StdioTransport(command=command, args=config["args"], cwd=str(cwd), env=env, keep_alive=False))

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *args):
        return await self.client.__aexit__(*args)

    async def call(self, name: str, arguments: dict):
        if name not in AGENT_TOOLS and not (self.human and name in {"authorize_payment", "confirm_purchase_order", "receive_purchase_order", "approve_and_pay", "reset_working_database"}):
            raise PermissionError("Tool is outside the allowed MCP interface.")
        response = await self.client.call_tool(name, arguments)
        return response.structured_content
