from pathlib import Path
root=Path(__file__).resolve().parent.parent
for name in ['mcp_server/README.md','backend/README.md','output/harness.md']:
    p=root/name
    s=p.read_text(encoding='utf-8')
    s=s.replace('sixteen tools: ten available to application agents','seventeen tools: eleven available to application agents')
    s=s.replace('four extension tables in the working copy: `approval_requests`, `board_drafts`, `purchase_order_drafts`, and `discount_decisions`','six extension tables in the working copy: `approval_requests`, `board_drafts`, `purchase_order_drafts`, `discount_decisions`, `ticket_resolutions`, and `supply_evidence`')
    s=s.replace('all four extension tables','all six extension tables')
    s+='''

## P9 final continuation — explicit decisions and provenance

The human approved invoice 501 ($840) and lease 1 rent ($2,400) through chat; the backend human payment routes recorded both approvals and payments. They also directed declining Ticket 103 for insufficient stock/funding, and explicitly permitted making up supplier/receipt information provided it is called out. Ticket 101's $8 quote, linked-invoice coverage, and one-unit receipt are therefore a user-authorized assignment simulation, not fetched supplier facts or physical observations. The original database remains untouched. No customer/vendor was contacted and no real bank transfer occurred.

### Added MCP tool

decline_ticket_request(ticket_id, rationale, customer_draft_id) is Boss-only. It reads tickets, board_drafts, approval_requests, purchase_order_drafts, and desk; writes ticket_resolutions and tickets. It closes only a price_override request, requires that ticket's customer draft, refuses pending payment requests and committed restocks, and records outcome=declined. It never fulfills an order, deducts stock, or spends cash. The older $52 proposal remains historical evidence and is superseded by the explicit decline.

### Additional database tables

- ticket_resolutions: ticket_id INTEGER PRIMARY KEY referencing tickets; outcome TEXT NOT NULL constrained to declined; rationale TEXT NOT NULL; customer_draft_id INTEGER NOT NULL referencing board_drafts; decided_at TEXT NOT NULL. Boss records the decision and Customer Service's unsent explanation. This distinguishes a declined request from fulfilled merchandise despite both using tickets.status=resolved.
- supply_evidence: id INTEGER PRIMARY KEY; purchase_order_id INTEGER NOT NULL referencing purchase_order_drafts; kind TEXT NOT NULL (quote/receipt); source TEXT NOT NULL (human_attestation/user_authorized_simulation); note TEXT NOT NULL; approved_by TEXT NOT NULL; recorded_at TEXT NOT NULL. Inventory, Accounting, Boss, and Customer Service must preserve this provenance rather than turn simulated goods into an assertion about real-world supply.

confirm_purchase_order and receive_purchase_order now also write supply_evidence. Their optional simulation_note labels the human-authorized exception; without it they record human_attestation. read_shop_board exposes both new tables, returning empty lists before creation. No agent can confirm quotes or receive goods. HTTP purchase confirmation and receipt bodies accept a nonempty simulation_note up to 1,000 characters; dashboard review forms expose optional simulation notes and change their attestations to explicitly authorize simulation instead of asserting physical verification. The private human credential stays outside all agent processes and logs.

All seventeen MCP tools are now documented: four reads, seven agent mutations (request_payment, save_board_draft, draft_purchase_order, record_discount_decision, fulfill_ticket_order, close_paid_rent_ticket, decline_ticket_request), and six human-only mutations (authorize_payment, execute_approved_payment, confirm_purchase_order, receive_purchase_order, approve_and_pay, reset_working_database). Role restrictions still apply; all twenty delegation edges remain available.

Validation: isolated decline test verifies explicit outcome and unchanged cash/stock, invalid type/draft refusal, and that a declined request cannot later be fulfilled. Five backend integration tests verify payment/receipt/provenance guards on disposable copies. Six frontend tests and TypeScript/Vite production build pass. Evidence: output/p9_decline_checks.log, output/p9_final_backend_checks.log, output/p9_final_frontend_checks.log, output/p9_final_frontend_build.log. No fixture receipt was applied to the real shop.
'''
    p.write_text(s,encoding='utf-8')
print('Current tool, table, route, and simulation provenance documentation updated.')
