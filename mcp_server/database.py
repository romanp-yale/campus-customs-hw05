"""Read-only ticket context from the existing working database."""

from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"


def read_ticket_context(ticket_id: int) -> dict[str, Any]:
    """Return stored rows only; raise errors rather than fabricate fallback data."""
    if ticket_id not in (101, 102, 103):
        raise ValueError("Only tickets 101, 102, and 103 are supported.")
    # mode=ro refuses a missing database instead of creating an empty one.
    with closing(sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")  # One consistent snapshot for all related reads.

        def rows(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

        tickets = rows("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if not tickets:
            raise ValueError(f"Ticket {ticket_id} is absent from the working database.")
        ticket = tickets[0]
        result = {
            "ticket": ticket,
            "desk": rows("SELECT * FROM desk"),
            "cash_accounts": rows("SELECT * FROM cash_accounts ORDER BY name"),
        }
        if ticket_id in (101, 103):
            result["inventory"] = rows(
                "SELECT * FROM inventory WHERE sku = ? AND size = ?",
                (ticket["sku"], ticket["size"]),
            )
            result["pricing"] = rows(
                "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],)
            )
        if ticket_id == 101:
            invoices = rows(
                "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)
            )
            result["linked_invoice"] = invoices
            result["linked_vendor"] = rows(
                "SELECT vendors.* FROM vendors JOIN invoices "
                "ON invoices.vendor_id = vendors.id WHERE invoices.id = ?",
                (ticket["invoice_id"],),
            )
            result["vendor_open_invoices"] = rows(
                "SELECT * FROM invoices WHERE status = ? AND vendor_id IN "
                "(SELECT vendor_id FROM invoices WHERE id = ?) ORDER BY id",
                ("open", ticket["invoice_id"]),
            )
        elif ticket_id == 102:
            result["lease"] = rows(
                "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)
            )
            # No enforced kind/ref_id convention yet: expose the ledger as stored.
            result["payments"] = rows("SELECT * FROM payments ORDER BY id")
        else:
            # No SKU/vendor mapping exists. Return the catalog, not guessed matches.
            result["vendors"] = rows("SELECT * FROM vendors ORDER BY id")
            result["open_invoices"] = rows(
                "SELECT * FROM invoices WHERE status = ? ORDER BY id", ("open",)
            )
        return result

ORIGINAL_DB_PATH = DB_PATH.with_name("campus_customs.db")
