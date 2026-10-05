"""Call the configured stdio MCP tools and independently verify their output."""

import asyncio
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sqlite3

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parent.parent
CASES = [
    (101, "get_ticket_101_tee_order_context", "Call get_ticket_101_tee_order_context with no arguments and return its database output for ticket 101 without adding assumptions."),
    (102, "get_ticket_102_rent_context", "Call get_ticket_102_rent_context with no arguments and return its database output for ticket 102 without adding assumptions."),
    (103, "get_ticket_103_hoodie_discount_context", "Call get_ticket_103_hoodie_discount_context with no arguments and return its database output for ticket 103 without adding assumptions."),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_output(conn: sqlite3.Connection, ticket_id: int) -> dict:
    """Independent SQL oracle; does not import the server's query implementation."""
    def rows(sql: str, params: tuple = ()) -> list:
        return [dict(row) for row in conn.execute(sql, params)]

    ticket = rows("SELECT * FROM tickets WHERE id = ?", (ticket_id,))[0]
    result = {"ticket": ticket, "desk": rows("SELECT * FROM desk"),
              "cash_accounts": rows("SELECT * FROM cash_accounts ORDER BY name")}
    if ticket_id in (101, 103):
        result["inventory"] = rows("SELECT * FROM inventory WHERE (sku, size) = (?, ?)", (ticket["sku"], ticket["size"]))
        result["pricing"] = rows("SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],))
    if ticket_id == 101:
        invoices = rows("SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],))
        result["linked_invoice"] = invoices
        vendor_ids = [invoice["vendor_id"] for invoice in invoices]
        result["linked_vendor"] = [row for row in rows("SELECT * FROM vendors ORDER BY id") if row["id"] in vendor_ids]
        result["vendor_open_invoices"] = [row for row in rows("SELECT * FROM invoices ORDER BY id") if row["vendor_id"] in vendor_ids and row["status"] == "open"]
    elif ticket_id == 102:
        result["lease"] = rows("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
        result["payments"] = rows("SELECT * FROM payments ORDER BY id")
    else:
        result["vendors"] = rows("SELECT * FROM vendors ORDER BY id")
        result["open_invoices"] = [row for row in rows("SELECT * FROM invoices ORDER BY id") if row["status"] == "open"]
    return result


async def main() -> None:
    config = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["campus_customs"]
    original = ROOT / "data/campus_customs.db"
    working = ROOT / "data/campus_customs_new.db"
    before = {"original": digest(original), "working": digest(working)}
    evidence = {
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "fastmcp_version": version("fastmcp"),
        "config": ".mcp.json",
        "transport": "stdio subprocess",
        "database": "data/campus_customs_new.db",
        "prompt_execution": "Exact assistant-authored test prompts mapped to direct MCP calls; no LLM or model API used.",
        "tests": [],
    }
    transport = StdioTransport(command=config["command"], args=config["args"], cwd=config["cwd"])
    async with Client(transport) as client:
        tools = await client.list_tools()
        evidence["discovered_tools"] = [tool.name for tool in tools]
        if not {name for _, name, _ in CASES}.issubset(evidence["discovered_tools"]):
            raise AssertionError("Server did not expose the three original ticket-context tools.")
        with closing(sqlite3.connect(working.as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN")
            for ticket_id, name, prompt in CASES:
                response = await client.call_tool(name, {})
                actual = response.structured_content
                expected = expected_output(conn, ticket_id)
                matches = actual == expected
                evidence["tests"].append({
                    "prompt": prompt, "tool_name": name, "arguments": {},
                    "returned_output": actual,
                    "content": [item.model_dump(mode="json", by_alias=True, exclude_none=True) for item in response.content],
                    "verification": {"matches_working_database": matches,
                                     "method": "Exact equality with independently queried full expected rows, keys, values, nulls, ordering, and empty lists."},
                })
                if not matches:
                    raise AssertionError(f"Output mismatch for {name}.")
    after = {"original": digest(original), "working": digest(working)}
    evidence["database_sha256_before"] = before
    evidence["database_sha256_after"] = after
    evidence["databases_unchanged"] = before == after
    if before != after:
        raise AssertionError("Database changed during the MCP test.")
    evidence["all_passed"] = True
    output = ROOT / "output/mcp_smoke.json"
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PASS: all three stdio MCP tools match the working database; evidence saved to {output}")


if __name__ == "__main__":
    asyncio.run(main())
