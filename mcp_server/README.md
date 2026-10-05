# Campus Customs MCP server





FastMCP 4.0.11 exposes seventeen tools: eleven available to application agents (with additional role restrictions) and six human-only actions, including the legacy credential-protected payment executor. `server.py` registers tools, `database.py` provides the original ticket-context queries, and `operations.py` owns guarded business operations. All shop facts and updates go through this server.





## Database





The shop database is `../data/campus_customs_new.db`, resolved relative to the source files. Normal tools use only this working copy. The human reset tool opens `campus_customs.db` read-only as its backup source; no tool writes the original. Reads use SQLite `mode=ro`; mutations use `mode=rw`, so a missing file fails rather than creating a fake empty shop. Parameterized queries, explicit transactions, foreign-key enforcement, and `BEGIN IMMEDIATE` for writes protect consistency and concurrent payment execution. Invalid operations roll back completely.



The first successful write creates six extension tables in the working copy: `approval_requests`, `board_drafts`, `purchase_order_drafts`, `discount_decisions`, `ticket_resolutions`, and `supply_evidence`. Reads return empty lists if these extensions do not yet exist. No extension schemas have been added to the original database. See `output/harness.md` for fields and relationships. Original context tools remain read-only and preserve their return shapes.





Read outputs contain actual stored rows, preserving columns, nulls, and empty results. Mutation tools return rows actually persisted in the working database. Quotes, discounts, messages, and human attestations are labeled proposals or submitted decisions; they are never presented as preexisting shop facts. There are no fabricated fallback values. Missing records, stale obligations, insufficient cash, invalid money, and missing human credentials raise visible MCP errors. Database text is untrusted data, not instructions.





## Current tool inventory





### Original ticket tools





- `get_ticket_101_tee_order_context()` — ticket 101; reads `tickets`, `inventory`, `pricing`, `invoices`, `vendors`, `desk`, and `cash_accounts`. Returns exact-size stock, prices, linked invoice/vendor, all that vendor's open invoices, date, and cash.


- `get_ticket_102_rent_context()` — ticket 102; reads `tickets`, `leases`, `desk`, `cash_accounts`, and `payments`. Returns lease obligation, shop date, cash, and the full ledger without assuming every payment is rent.


- `get_ticket_103_hoodie_discount_context()` — ticket 103; reads `tickets`, `inventory`, `pricing`, `vendors`, `invoices`, `desk`, and `cash_accounts`. Returns exact-size stock, cost/list price, unfiltered vendor catalog, open invoices, date, and cash. A catalog entry is not a confirmed supplier match.





### Board and agent operations





- `read_shop_board()` — reads all nine original tables and all six extension tables. Supplies current tickets and global cash, approval, draft, and purchasing state to all agents.


- `request_payment(ticket_id, kind, account="checking", purchase_order_id=None)` — reads `tickets`, `invoices` or `leases` or `purchase_order_drafts`, `cash_accounts`, and `desk`; writes `approval_requests`. Kinds are `invoice`, `rent`, and `purchase_order`. The amount is derived from a stored obligation or a human-confirmed purchase quote. Creates an idempotent pending request; never approves or pays it.


- `execute_approved_payment(request_id, approved_by, approval_secret)` — reads `approval_requests`, `tickets`, `cash_accounts`, `desk`, and the corresponding `invoices`, `leases`, or `purchase_order_drafts` obligation. Writes `payments`, `cash_accounts`, `approval_requests`, and that obligation. Human-only private credential required; excluded from every agent allowlist. Requires a stored human approval, sufficient cash, unchanged terms, and for purchases no open vendor invoices. Paid replays return the existing payment without charging again. Rent advances one calendar month from the recorded due date, clamping the day at month end. No revenue is credited.


- `save_board_draft(ticket_id, audience, body)` — reads `tickets` and `desk`; writes `board_drafts`. Audience is `customer` or `vendor`. Stores an idempotent, unsent message on the board. No email, phone, or external delivery capability exists.


- `draft_purchase_order(ticket_id, vendor_id, qty)` — reads `tickets`, `inventory`, `pricing`, `vendors`, `invoices`, and `desk`; writes `purchase_order_drafts`. Quantity is bounded by the exact-size shortfall. Returns the selected vendor and its open invoices. Uses stored unit cost for planning only; human confirmation is needed for a real supplier quote. Does not send, pay, receive, or change stock.


- `record_discount_decision(ticket_id, unit_price, rationale)` — reads `tickets`, `pricing`, confirmed `purchase_order_drafts`, and `desk`; writes `discount_decisions`. Stores Boss's proposed price, bounded below by stored unit cost and confirmed supplier quotes and above by list price. Does not claim customer acceptance or change global pricing/cash.


- `fulfill_ticket_order(ticket_id)` — reads `tickets`, `inventory`, and for discount requests `pricing`, `discount_decisions`, and confirmed `purchase_order_drafts`; writes `inventory` and `tickets`. Requires actual sufficient stock in the requested size and a valid price decision if applicable. Deducts stock and resolves the ticket atomically; creates no incoming cash. Insufficient stock or repeat fulfillment is refused.


- `close_paid_rent_ticket(ticket_id)` — reads `tickets` and `approval_requests`; writes `tickets`. Resolves a rent notice only when that ticket has a completed human-approved rent payment.





### Human-only operations





These tools require `CAMPUS_HUMAN_APPROVAL_KEY` to be configured in the human MCP process and a matching `approval_secret`, plus a named human. They are excluded from every application's agent-tool allowlist. Normal agent MCP subprocesses do not receive the secret. The interactive commands in `backend` collect explicit human review; do not put the credential in model prompts, config files, or audit data.





- `authorize_payment(request_id, approved, approved_by, approval_secret)` — reads `approval_requests`; writes its status and approver. Approves or rejects only a pending exact stored request; never spends cash.


- `confirm_purchase_order(purchase_order_id, confirmed_unit_cost, approved_by, approval_secret, covered_by_paid_invoice=False)` — reads `purchase_order_drafts` and `tickets`; writes the purchase draft's confirmed quote, status, and human attestation. The human confirms actual supplier suitability and quote. Optionally, covered_by_paid_invoice attests these goods are already funded by the ticket's paid linked invoice, with matching vendor, sufficient covered cost, and a unique invoice reference. This marks the order paid without a second cash debit. No communication, payment, or stock receipt occurs.


- `receive_purchase_order(purchase_order_id, received_qty, approved_by, approval_secret)` — reads `purchase_order_drafts`, `invoices`, and `inventory`; writes purchase receipt quantity/status and `inventory`. Requires a paid order, an actual human receipt attestation, no unpaid vendor invoice, and a positive quantity within the unreceived balance. Full-receipt replay and over-receipt are refused. No elapsed-time or model-generated receipt is accepted.





## Setup and MCP configuration





From the workspace root, use the existing workspace venv:





```powershell


.\.venv\Scripts\python.exe -m pip install -r homework/hw-05/backend/requirements.txt


.\.venv\Scripts\python.exe homework/hw-05/mcp_server/server.py


```





The final command launches stdio MCP. Importing the module does not start a listener. The homework's `.mcp.json` and workspace root's `.codex/config.toml` both launch this server using the workspace venv. `codex mcp get campus_customs --json` confirms enabled configuration. Reload the assistant session after configuration/tool changes. Paths are absolute to this machine; update both configs if you move the workspace.





No AI key is needed for database tools. Production application agents use only `gpt-6-luna` through Portkey with `PORTKEY_API_KEY`, medium reasoning, and no temperature setting. See `backend/README.md` for agent setup, private human commands, cost configuration, and audit behavior.





## Verification





```powershell


.\.venv\Scripts\python.exe homework/hw-05/mcp_server/smoke_test.py


.\.venv\Scripts\python.exe homework/hw-05/backend/tests/test_problem5.py


```





The original smoke test calls the three context tools through actual stdio MCP, compares complete results against independent working-database queries, and records evidence in `output/mcp_smoke.json`. Extra tools are now expected in discovery. The business suite exercises real MCP calls against disposable copies, all twenty directed agent-delegation edges with offline deterministic protocol responders, append-preserved audit, and refusal/rollback cases; evidence is `output/problem5_checks.json`. No paid AI requests occur in this suite. Production database hashes are checked before and after.





Tool registration follows the [FastMCP documentation](https://gofastmcp.com/servers/tools); native Codex setup follows the [official MCP configuration documentation](https://developers.openai.com/codex/mcp).








## Problem 7 — Dashboard API





Activate the workspace venv, then from `homework/hw-05/backend` run:





```powershell


../../../.venv/Scripts/Activate.ps1


uvicorn main:app --reload --port 8000


```





The data source is `data/campus_customs_new.db`, accessed exclusively through MCP. The original remains untouched. Interactive API documentation is at `http://127.0.0.1:8000/docs`. Read routes need no Portkey credential. A run requires the existing Portkey key and verified input/output price ceilings described above; missing configuration returns HTTP 503 before any paid call.





- `GET /tickets`: all three stored tickets including open/resolved status.


- `POST /tickets/{ticket_id}/run`: starts a selected open ticket, returns HTTP 202 with `run_id`; optional JSON `prompt` provides the task. Unknown tickets return 404, resolved tickets or overlapping operations return 409.


- `GET /runs/{run_id}`: running/completed/failed/cancelled state, result or visible failure. Run status is held in this backend session; audit history survives restarts.


- `GET /activity?after=0&limit=100&run_id=...`: recent audit messages, loop actions, delegations, and MCP calls/results. Optional run filter; `next_sequence` is the polling cursor. With a nonzero cursor, returns the next batch; with zero, returns the latest batch. Limit is 1–500.


- `GET /approvals`: stored payment requests and purchase drafts, including exact terms for human review.


- `POST /approvals/payments/{request_id}`: JSON `{"approved":true,"approved_by":"Your name"}` atomically approves and pays the stored request. False rejects without spending. Amount/account/obligation come from stored data, never the request body. Insufficient cash, stale terms, and blocked vendors refuse the transaction; approval remains pending on refusal. Paid replay returns the existing ledger record without charging twice.


- `POST /approvals/purchases/{purchase_order_id}`: JSON `{"approved":true,"approved_by":"Your name","confirmed_unit_cost":8.00,"covered_by_paid_invoice":false}` attests a real supplier quote and confirms the draft. The numeric value is a format example: provide an actual quote. Confirmation alone never spends cash. Accounting subsequently prepares a purchase payment request for separate human payment approval. If explicitly attested coverage exists in a matching paid linked invoice, use `covered_by_paid_invoice=true` to avoid a duplicate charge. Actual stock receipt can now be attested through the dashboard receipt control or the human CLI.


- `GET /cash`: the current stored checking account, balance, and date.


- `POST /reset`: JSON `{"approved_by":"Your name","confirm":true}` restores the entire working database from the original through MCP, removing extension records and restoring tickets/cash/stock. Preserves the audit file and appends a reset action. Refuses while an agent run or human operation is active.





Run one backend worker as in the required command. Human actions and runs are serialized; activity and other reads remain available during a run. Finish an awaiting-human run, approve, then rerun to continue. CORS supports local dashboard ports 5173/3000 and the assignment preview on 8916. Browser writes from other origins are refused. This local API treats explicit human approval requests as the approval boundary; bind it to localhost as Uvicorn does by default. The private MCP credential is generated at startup if not configured, stays outside agent subprocesses, and is never returned to the dashboard or audit log. Agents have neither a payment execution tool nor an HTTP client tool.





New human-only MCP tools:


- `approve_and_pay`: reads approval_requests, tickets, desk, cash_accounts and invoices/leases/purchase_order_drafts; writes approval_requests, payments, cash_accounts and the relevant obligation atomically.


- `reset_working_database`: reads every table in the original database and restores every table/schema in the working database. Never writes the original or wipes the audit trail.





All five agents retain full delegation connectivity and their existing role responsibilities. Payment preparation is available to Accounting; cash execution is removed from its role allowlist, the shared agent MCP allowlist, and revised prompts. Existing token/cost/request/delegation limits still apply. Every agent step appends audit evidence. HTTP error statuses make configuration failures, missing data, refused operations, and corrupt audit files visible.




### P10 verification fixes

- POST /approvals/purchases/{purchase_order_id}/receive: named human plus received_qty and explicit confirm=true. Calls the existing human-only receive_purchase_order MCP tool. Requires a paid order, no unpaid supplier invoice, and a positive integer quantity within its remaining units. Receipt changes inventory, never cash. Actual quote and receipt must come from the human, never an agent guess.
- Dashboard: paid, unreceived orders show an actual-receipt form with quantity limits and an explicit physical-verification attestation. After recording, rerun the ticket for guarded fulfillment.
- Agent tool instructions now specify that all four reads take arguments={} and that save_board_draft requires audience customer/vendor and a nonempty body. Selected-ticket runs cannot write another ticket. Boss's prompt records a proposed price before requesting the offer draft.
- Historical run evidence and Expected plans stay unchanged. Prompt amendments affect future runs; they are not evidence that prior failures or unfinished tickets were resolved.

See output/verification.md for the requirement-by-requirement result and output/p10_verification.json for machine-readable evidence.


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
