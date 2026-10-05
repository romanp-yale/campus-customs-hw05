"""Guarded shop operations. This module runs only inside the MCP server."""

from calendar import monthrange
from contextlib import contextmanager, closing
from datetime import date
from decimal import Decimal
import hmac
import os
import sqlite3

if __package__:
    from . import database
else:
    import database

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS approval_requests (id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), kind TEXT NOT NULL CHECK(kind IN ('invoice','rent','purchase_order')), ref_id INTEGER NOT NULL, obligation_date TEXT NOT NULL, amount REAL NOT NULL CHECK(amount > 0), account TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','paid')), approved_by TEXT, requested_at TEXT NOT NULL, payment_id INTEGER REFERENCES payments(id), UNIQUE(kind,ref_id,obligation_date,account))",
    "CREATE TABLE IF NOT EXISTS board_drafts (id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), audience TEXT NOT NULL CHECK(audience IN ('customer','vendor')), body TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(ticket_id,audience,body))",
    "CREATE TABLE IF NOT EXISTS purchase_order_drafts (id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), vendor_id INTEGER NOT NULL REFERENCES vendors(id), sku TEXT NOT NULL, size TEXT NOT NULL, qty INTEGER NOT NULL CHECK(qty > 0), unit_cost REAL NOT NULL, status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL, confirmed_by TEXT, received_qty INTEGER NOT NULL DEFAULT 0, funding_invoice_id INTEGER UNIQUE REFERENCES invoices(id), UNIQUE(ticket_id,vendor_id,sku,size,qty))",
    "CREATE TABLE IF NOT EXISTS discount_decisions (ticket_id INTEGER PRIMARY KEY REFERENCES tickets(id), unit_price REAL NOT NULL CHECK(unit_price > 0), rationale TEXT NOT NULL, decided_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS ticket_resolutions (ticket_id INTEGER PRIMARY KEY REFERENCES tickets(id), outcome TEXT NOT NULL CHECK(outcome='declined'), rationale TEXT NOT NULL, customer_draft_id INTEGER NOT NULL REFERENCES board_drafts(id), decided_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS supply_evidence (id INTEGER PRIMARY KEY, purchase_order_id INTEGER NOT NULL REFERENCES purchase_order_drafts(id), kind TEXT NOT NULL CHECK(kind IN ('quote','receipt')), source TEXT NOT NULL CHECK(source IN ('human_attestation','user_authorized_simulation')), note TEXT NOT NULL, approved_by TEXT NOT NULL, recorded_at TEXT NOT NULL)",
)
ADDITIONAL_TABLES = ("approval_requests", "board_drafts", "purchase_order_drafts", "discount_decisions", "ticket_resolutions", "supply_evidence")


@contextmanager
def connection(write: bool = False):
    conn = sqlite3.connect(database.DB_PATH.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        if write:
            for sql in SCHEMA:
                conn.execute(sql)
        yield conn
        if write:
            conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    if row is None:
        raise ValueError("Required database record is missing.")
    return dict(row)


def shop_date(conn):
    rows = conn.execute("SELECT date_today FROM desk").fetchall()
    if len(rows) != 1:
        raise ValueError("desk must contain exactly one shop date.")
    return date.fromisoformat(rows[0]["date_today"]).isoformat()


def ticket(conn, ticket_id):
    row = one(conn, "SELECT * FROM tickets WHERE id=?", (ticket_id,))
    if row["status"] != "open":
        raise ValueError("Ticket is not open.")
    return row


def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Money must be finite, nonnegative, and exact to cents.")
    return amount


def read_shop_board():
    with connection() as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        tables = ("desk", "tickets", "inventory", "pricing", "vendors", "leases", "cash_accounts", "payments", "invoices", *ADDITIONAL_TABLES)
        return {name: [dict(r) for r in conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid')] if name in names else [] for name in tables}


def request_payment(ticket_id: int, kind: str, account: str, purchase_order_id: int | None = None):
    if kind not in ("invoice", "rent", "purchase_order"):
        raise ValueError("Payment kind must be invoice, rent, or purchase_order.")
    with connection(True) as conn:
        t = ticket(conn, ticket_id)
        one(conn, "SELECT * FROM cash_accounts WHERE name=?", (account,))
        if kind == "invoice":
            ref_id = t["invoice_id"]
            obligation = one(conn, "SELECT * FROM invoices WHERE id=?", (ref_id,))
            if obligation["status"] != "open":
                raise ValueError("Invoice is not open.")
            amount, due = money(obligation["amount"]), obligation["due_date"]
        elif kind == "rent":
            ref_id = t["lease_id"]
            obligation = one(conn, "SELECT * FROM leases WHERE id=?", (ref_id,))
            amount, due = money(obligation["monthly_rent"]), obligation["next_due"]
        else:
            ref_id = purchase_order_id
            obligation = one(conn, "SELECT * FROM purchase_order_drafts WHERE id=? AND ticket_id=?", (ref_id,ticket_id))
            if obligation["status"] != "confirmed" or not obligation["confirmed_by"]:
                raise ValueError("A human must confirm the supplier and quote before requesting purchase payment.")
            amount, due = money(obligation["unit_cost"])*obligation["qty"], obligation["created_at"]
        if amount <= 0:
            raise ValueError("Payment amount must be positive.")
        conn.execute("INSERT OR IGNORE INTO approval_requests (ticket_id,kind,ref_id,obligation_date,amount,account,status,requested_at) VALUES (?,?,?,?,?,?,'pending',?)", (ticket_id,kind,ref_id,due,float(amount),account,shop_date(conn)))
        return one(conn, "SELECT * FROM approval_requests WHERE kind=? AND ref_id=? AND obligation_date=? AND account=?", (kind,ref_id,due,account))


def require_human(approved_by: str, approval_secret: str):
    expected = os.getenv("CAMPUS_HUMAN_APPROVAL_KEY", "")
    if not expected or not hmac.compare_digest(expected, approval_secret):
        raise PermissionError("Human approval credential is invalid or not configured.")
    if not approved_by.strip() or len(approved_by) > 120:
        raise ValueError("A human approver name is required.")


def authorize_payment(request_id: int, approved: bool, approved_by: str, approval_secret: str):
    require_human(approved_by,approval_secret)
    with connection(True) as conn:
        req = one(conn, "SELECT * FROM approval_requests WHERE id=?", (request_id,))
        if req["status"] != "pending":
            raise ValueError("Only pending requests can be approved or rejected.")
        conn.execute("UPDATE approval_requests SET status=?, approved_by=? WHERE id=?", ("approved" if approved else "rejected",approved_by.strip(),request_id))
        return one(conn, "SELECT * FROM approval_requests WHERE id=?", (request_id,))


def execute_approved_payment(request_id: int, approved_by: str, approval_secret: str):
    require_human(approved_by, approval_secret)
    with connection(True) as conn:
        return _execute_payment(conn, request_id)


def approve_and_pay(request_id: int, approved: bool, approved_by: str, approval_secret: str):
    """Human HTTP approval: decision and debit commit or roll back together."""
    require_human(approved_by, approval_secret)
    with connection(True) as conn:
        req = one(conn, "SELECT * FROM approval_requests WHERE id=?", (request_id,))
        if req['status'] == 'paid' and approved:
            return _execute_payment(conn, request_id)
        if req['status'] != 'pending':
            raise ValueError('Only pending requests can receive a new decision.')
        conn.execute("UPDATE approval_requests SET status=?, approved_by=? WHERE id=?",
                     ('approved' if approved else 'rejected', approved_by.strip(), request_id))
        if not approved:
            return one(conn, "SELECT * FROM approval_requests WHERE id=?", (request_id,))
        return _execute_payment(conn, request_id)


def _execute_payment(conn, request_id):
    req = one(conn, "SELECT * FROM approval_requests WHERE id=?", (request_id,))
    if req["status"] == "paid":
        return one(conn, "SELECT * FROM payments WHERE id=?", (req["payment_id"],))
    if req["status"] != "approved" or not req["approved_by"]:
        raise PermissionError("Payment requires a stored human approval.")
    ticket(conn, req["ticket_id"])
    amount = money(req["amount"])
    account = one(conn, "SELECT * FROM cash_accounts WHERE name=?", (req["account"],))
    balance = money(account["balance"])
    if balance < amount:
        raise ValueError("Insufficient cash; payment refused.")
    if req["kind"] == "invoice":
        obligation = one(conn, "SELECT * FROM invoices WHERE id=?", (req["ref_id"],))
        if obligation["status"] != "open" or money(obligation["amount"]) != amount or obligation["due_date"] != req["obligation_date"]:
            raise ValueError("Invoice changed since approval or was already paid.")
        conn.execute("UPDATE invoices SET status='paid' WHERE id=?", (req["ref_id"],))
    elif req["kind"] == "rent":
        obligation = one(conn, "SELECT * FROM leases WHERE id=?", (req["ref_id"],))
        if obligation["next_due"] != req["obligation_date"] or money(obligation["monthly_rent"]) != amount:
            raise ValueError("Rent obligation changed since approval or was already paid.")
        due = date.fromisoformat(obligation["next_due"])
        year, month = (due.year+1,1) if due.month==12 else (due.year,due.month+1)
        next_due = date(year,month,min(due.day,monthrange(year,month)[1])).isoformat()
        conn.execute("UPDATE leases SET next_due=? WHERE id=?", (next_due,req["ref_id"]))
    else:
        obligation=one(conn,"SELECT * FROM purchase_order_drafts WHERE id=?",(req["ref_id"],))
        if obligation["status"]!="confirmed" or money(obligation["unit_cost"])*obligation["qty"]!=amount or obligation["created_at"]!=req["obligation_date"]:
            raise ValueError("Purchase order changed since approval or was already paid.")
        if conn.execute("SELECT 1 FROM invoices WHERE vendor_id=? AND status='open'",(obligation["vendor_id"],)).fetchone():
            raise ValueError("Vendor cannot ship while an invoice remains unpaid; purchase payment refused.")
        conn.execute("UPDATE purchase_order_drafts SET status='paid' WHERE id=?",(req["ref_id"],))
    today = shop_date(conn)
    conn.execute("UPDATE cash_accounts SET balance=?, date=? WHERE name=?", (float(balance-amount),today,req["account"]))
    cursor = conn.execute("INSERT INTO payments (kind,ref_id,amount,account,paid_at,approved_by) VALUES (?,?,?,?,?,?)", (req["kind"],req["ref_id"],float(amount),req["account"],today,req["approved_by"]))
    conn.execute("UPDATE approval_requests SET status='paid', payment_id=? WHERE id=?", (cursor.lastrowid,request_id))
    return one(conn, "SELECT * FROM payments WHERE id=?", (cursor.lastrowid,))


def save_board_draft(ticket_id: int, audience: str, body: str):
    if audience not in ("customer", "vendor") or not body.strip() or len(body) > 8000:
        raise ValueError("Provide a customer/vendor draft of 1–8000 characters.")
    with connection(True) as conn:
        ticket(conn,ticket_id)
        conn.execute("INSERT OR IGNORE INTO board_drafts (ticket_id,audience,body,created_at) VALUES (?,?,?,?)", (ticket_id,audience,body,shop_date(conn)))
        return one(conn, "SELECT * FROM board_drafts WHERE ticket_id=? AND audience=? AND body=?", (ticket_id,audience,body))


def draft_purchase_order(ticket_id: int, vendor_id: int, qty: int):
    if isinstance(qty,bool) or qty <= 0:
        raise ValueError("Purchase quantity must be a positive integer.")
    with connection(True) as conn:
        t = ticket(conn,ticket_id)
        if t["type"] not in ("customer_order", "price_override"):
            raise ValueError("Ticket is not a merchandise request.")
        vendor = one(conn,"SELECT * FROM vendors WHERE id=?",(vendor_id,))
        stock = one(conn,"SELECT * FROM inventory WHERE sku=? AND size=?",(t["sku"],t["size"]))
        if qty > max(0,t["qty"]-stock["qty"]):
            raise ValueError("Draft quantity exceeds the current ticket shortfall.")
        pricing = one(conn,"SELECT * FROM pricing WHERE sku=?",(t["sku"],))
        conn.execute("INSERT OR IGNORE INTO purchase_order_drafts (ticket_id,vendor_id,sku,size,qty,unit_cost,created_at) VALUES (?,?,?,?,?,?,?)",(ticket_id,vendor_id,t["sku"],t["size"],qty,pricing["unit_cost"],shop_date(conn)))
        draft = one(conn,"SELECT * FROM purchase_order_drafts WHERE ticket_id=? AND vendor_id=? AND sku=? AND size=? AND qty=?",(ticket_id,vendor_id,t["sku"],t["size"],qty))
        unpaid = [dict(r) for r in conn.execute("SELECT * FROM invoices WHERE vendor_id=? AND status='open' ORDER BY id",(vendor_id,))]
        return {"draft":draft,"vendor":vendor,"open_invoices":unpaid}


def record_discount_decision(ticket_id: int, unit_price: float, rationale: str):
    price = money(unit_price)
    if not rationale.strip() or len(rationale)>4000:
        raise ValueError("A pricing rationale of 1–4000 characters is required.")
    with connection(True) as conn:
        t=ticket(conn,ticket_id)
        if t["type"] != "price_override":
            raise ValueError("Ticket is not a price override.")
        pricing=one(conn,"SELECT * FROM pricing WHERE sku=?",(t["sku"],))
        quoted=conn.execute("SELECT MAX(unit_cost) FROM purchase_order_drafts WHERE ticket_id=? AND status!='draft'",(ticket_id,)).fetchone()[0]
        floor=max(money(pricing["unit_cost"]),money(quoted) if quoted is not None else Decimal(0))
        if price < floor or price > money(pricing["list_price"]) or price<=0:
            raise ValueError("Price must cover stored cost and confirmed supplier quotes without exceeding list price.")
        conn.execute("INSERT INTO discount_decisions VALUES (?,?,?,?) ON CONFLICT(ticket_id) DO UPDATE SET unit_price=excluded.unit_price,rationale=excluded.rationale,decided_at=excluded.decided_at",(ticket_id,float(price),rationale,shop_date(conn)))
        return one(conn,"SELECT * FROM discount_decisions WHERE ticket_id=?",(ticket_id,))


def fulfill_ticket_order(ticket_id: int):
    with connection(True) as conn:
        t=ticket(conn,ticket_id)
        if t["type"] not in ("customer_order","price_override"):
            raise ValueError("Ticket is not a merchandise order.")
        if not isinstance(t["qty"],int) or t["qty"]<=0:
            raise ValueError("Ticket quantity must be positive.")
        if t["type"]=="price_override":
            decision=one(conn,"SELECT * FROM discount_decisions WHERE ticket_id=?",(ticket_id,))
            pricing=one(conn,"SELECT * FROM pricing WHERE sku=?",(t["sku"],))
            quoted=conn.execute("SELECT MAX(unit_cost) FROM purchase_order_drafts WHERE ticket_id=? AND status!='draft'",(ticket_id,)).fetchone()[0]
            floor=max(money(pricing["unit_cost"]),money(quoted) if quoted is not None else Decimal(0))
            if not floor<=money(decision["unit_price"])<=money(pricing["list_price"]):
                raise ValueError("Pricing changed since the decision.")
        stock=one(conn,"SELECT * FROM inventory WHERE sku=? AND size=?",(t["sku"],t["size"]))
        if stock["qty"]<t["qty"]:
            raise ValueError("Insufficient exact-size stock; proposed restocks do not count.")
        conn.execute("UPDATE inventory SET qty=qty-? WHERE sku=? AND size=?",(t["qty"],t["sku"],t["size"]))
        conn.execute("UPDATE tickets SET status='resolved' WHERE id=?",(ticket_id,))
        return {"ticket":one(conn,"SELECT * FROM tickets WHERE id=?",(ticket_id,)),"inventory":one(conn,"SELECT * FROM inventory WHERE sku=? AND size=?",(t["sku"],t["size"]))}


def close_paid_rent_ticket(ticket_id: int):
    with connection(True) as conn:
        t=ticket(conn,ticket_id)
        if t["type"] != "rent_notice":
            raise ValueError("Ticket is not a rent notice.")
        one(conn,"SELECT * FROM approval_requests WHERE ticket_id=? AND kind='rent' AND status='paid'",(ticket_id,))
        conn.execute("UPDATE tickets SET status='resolved' WHERE id=?",(ticket_id,))
        return one(conn,"SELECT * FROM tickets WHERE id=?",(ticket_id,))


def decline_ticket_request(ticket_id: int, rationale: str, customer_draft_id: int):
    """Close a price request with an explicit decline; never imply fulfillment."""
    if not rationale.strip() or len(rationale)>4000:
        raise ValueError('A decline requires a rationale of 1–4000 characters.')
    with connection(True) as conn:
        t=ticket(conn,ticket_id)
        if t['type']!='price_override':
            raise ValueError('Only a price-override request can be declined with this tool.')
        one(conn,"SELECT * FROM board_drafts WHERE id=? AND ticket_id=? AND audience='customer'",(customer_draft_id,ticket_id))
        if conn.execute("SELECT 1 FROM approval_requests WHERE ticket_id=? AND status IN ('pending','approved')",(ticket_id,)).fetchone():
            raise ValueError('Resolve pending payment requests before declining the ticket.')
        if conn.execute("SELECT 1 FROM purchase_order_drafts WHERE ticket_id=? AND status IN ('confirmed','paid')",(ticket_id,)).fetchone():
            raise ValueError('A committed restock requires separate review before decline.')
        conn.execute('INSERT INTO ticket_resolutions VALUES (?,?,?,?,?)',(ticket_id,'declined',rationale.strip(),customer_draft_id,shop_date(conn)))
        conn.execute("UPDATE tickets SET status='resolved' WHERE id=?",(ticket_id,))
        return {'ticket':one(conn,'SELECT * FROM tickets WHERE id=?',(ticket_id,)),
                'resolution':one(conn,'SELECT * FROM ticket_resolutions WHERE ticket_id=?',(ticket_id,))}


def record_supply_evidence(conn, order_id, kind, actor, simulation_note):
    if simulation_note is not None and (not simulation_note.strip() or len(simulation_note)>1000):
        raise ValueError('Simulation note must contain 1–1000 characters.')
    conn.execute('INSERT INTO supply_evidence (purchase_order_id,kind,source,note,approved_by,recorded_at) VALUES (?,?,?,?,?,?)',
                 (order_id,kind,'user_authorized_simulation' if simulation_note is not None else 'human_attestation',
                  simulation_note.strip() if simulation_note is not None else 'Human attested supplier quote or actual physical receipt.',actor.strip(),shop_date(conn)))


def confirm_purchase_order(purchase_order_id: int, confirmed_unit_cost: float, approved_by: str, approval_secret: str, covered_by_paid_invoice: bool = False, simulation_note: str | None = None):
    require_human(approved_by,approval_secret)
    cost=money(confirmed_unit_cost)
    if cost<=0:
        raise ValueError("Confirmed supplier cost must be positive.")
    with connection(True) as conn:
        order=one(conn,"SELECT * FROM purchase_order_drafts WHERE id=?",(purchase_order_id,))
        t=ticket(conn,order["ticket_id"])
        if order["status"]!="draft":
            raise ValueError("Only an unconfirmed draft can be confirmed.")
        funding_id=None
        if covered_by_paid_invoice:
            invoice=one(conn,"SELECT * FROM invoices WHERE id=?",(t["invoice_id"],))
            if invoice["status"]!="paid" or invoice["vendor_id"]!=order["vendor_id"] or cost*order["qty"]>money(invoice["amount"]):
                raise ValueError("Linked invoice must be paid, belong to this vendor, and cover the attested goods cost.")
            funding_id=invoice["id"]
        conn.execute("UPDATE purchase_order_drafts SET unit_cost=?,status=?,confirmed_by=?,funding_invoice_id=? WHERE id=?",(float(cost),"paid" if funding_id is not None else "confirmed",approved_by.strip(),funding_id,purchase_order_id))
        record_supply_evidence(conn,purchase_order_id,'quote',approved_by,simulation_note)
        return one(conn,"SELECT * FROM purchase_order_drafts WHERE id=?",(purchase_order_id,))


def receive_purchase_order(purchase_order_id: int, received_qty: int, approved_by: str, approval_secret: str, simulation_note: str | None = None):
    require_human(approved_by,approval_secret)
    with connection(True) as conn:
        order=one(conn,"SELECT * FROM purchase_order_drafts WHERE id=?",(purchase_order_id,))
        if order["status"]!="paid" or not isinstance(received_qty,int) or isinstance(received_qty,bool) or received_qty<=0 or received_qty>order["qty"]-order["received_qty"]:
            raise ValueError("Receipt must be a positive remaining quantity on a paid purchase order.")
        if conn.execute("SELECT 1 FROM invoices WHERE vendor_id=? AND status='open'",(order["vendor_id"],)).fetchone():
            raise ValueError("Vendor cannot ship while an invoice remains unpaid.")
        one(conn,"SELECT * FROM inventory WHERE sku=? AND size=?",(order["sku"],order["size"]))
        conn.execute("UPDATE inventory SET qty=qty+? WHERE sku=? AND size=?",(received_qty,order["sku"],order["size"]))
        total=order["received_qty"]+received_qty
        conn.execute("UPDATE purchase_order_drafts SET received_qty=?,status=? WHERE id=?",(total,"received" if total==order["qty"] else "paid",purchase_order_id))
        record_supply_evidence(conn,purchase_order_id,'receipt',approved_by,simulation_note)
        return {"purchase_order":one(conn,"SELECT * FROM purchase_order_drafts WHERE id=?",(purchase_order_id,)),"inventory":one(conn,"SELECT * FROM inventory WHERE sku=? AND size=?",(order["sku"],order["size"]))}


def reset_working_database(approved_by: str, approval_secret: str):
    require_human(approved_by, approval_secret)
    original = database.ORIGINAL_DB_PATH.resolve()
    working = database.DB_PATH.resolve()
    if original == working:
        raise ValueError('Original and working database must be different files.')
    with closing(sqlite3.connect(original.as_uri() + '?mode=ro', uri=True)) as source:
        if source.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Original database integrity check failed.')
        with closing(sqlite3.connect(working.as_uri() + '?mode=rw', uri=True)) as destination:
            source.backup(destination)
    return {'reset': True, 'board': read_shop_board()}
