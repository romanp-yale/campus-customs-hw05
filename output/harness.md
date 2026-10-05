# Campus Customs database and agent harness





This harness retains the original database inspection and documents Problems 3–5 below.





## Source and preservation





Inspected every table, field, declared foreign key, and existing row in `data/campus_customs.db` using a read-only SQLite connection. The original database was not modified. `data/campus_customs_new.db` is a refreshed byte-for-byte copy and is the database for all future changes.





Original and working-copy SHA-256: `23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a`.





There are nine tables. All fields have no declared default value. Field constraints below reflect the actual SQLite declarations; integer primary keys are identifiers even though SQLite reports their PRAGMA notnull flag as zero. Text primary keys below have no explicit NOT NULL declaration.





## Tables and fields





### cash_accounts





Initial rows: 1.





Accounting checks available cash here before proposing payments for the human route. The pay tool must refuse insufficient funds and prevent negative balances; no revenue is modeled.





Fields:





- `name` — `TEXT`; primary key, no explicit NOT NULL declaration.


- `balance` — `REAL`; NOT NULL.


- `date` — `TEXT`; NOT NULL.





### desk





Initial rows: 1.





All agents use date_today as the shop clock for overdue invoices and upcoming rent, rather than the computer date. Notes can hold shared shop context.





Fields:





- `date_today` — `TEXT`; NOT NULL.


- `notes` — `TEXT`; nullable.





### inventory





Initial rows: 10.





Inventory checks availability by SKU and size, identifies shortfalls, and locates stock. Boss and Customer Service use the result to decide whether an order can be fulfilled.





Fields:





- `sku` — `TEXT`; primary key component 1, NOT NULL.


- `name` — `TEXT`; NOT NULL.


- `size` — `TEXT`; primary key component 2, NOT NULL.


- `qty` — `INTEGER`; NOT NULL.


- `location` — `TEXT`; NOT NULL.





Composite primary key: `(sku, size)`.





### invoices





Initial rows: 1.





Accounting identifies unpaid vendor obligations and prepares payment approval requests. Inventory checks these obligations because a vendor with an open unpaid invoice will not ship.





Fields:





- `id` — `INTEGER`; primary key, no explicit NOT NULL declaration.


- `vendor_id` — `INTEGER`; NOT NULL.


- `amount` — `REAL`; NOT NULL.


- `due_date` — `TEXT`; NOT NULL.


- `status` — `TEXT`; NOT NULL.


- `description` — `TEXT`; nullable.





Declared foreign key: `invoices.vendor_id` → `vendors.id` (ON UPDATE / ON DELETE: NO ACTION).





### leases





Initial rows: 1.





Facilities checks rent obligations and due dates; Accounting prepares the associated payment for human approval and updates the relevant lease record after payment.





Fields:





- `id` — `INTEGER`; primary key, no explicit NOT NULL declaration.


- `space_name` — `TEXT`; NOT NULL.


- `landlord` — `TEXT`; NOT NULL.


- `monthly_rent` — `REAL`; NOT NULL.


- `next_due` — `TEXT`; NOT NULL.


- `notes` — `TEXT`; nullable.





### payments





Initial rows: 0.





Accounting records completed payments and the approving human. Boss and the dashboard use this audit trail to distinguish proposed payments from completed ones.





Fields:





- `id` — `INTEGER`; primary key, no explicit NOT NULL declaration.


- `kind` — `TEXT`; NOT NULL.


- `ref_id` — `INTEGER`; nullable.


- `amount` — `REAL`; NOT NULL.


- `account` — `TEXT`; NOT NULL.


- `paid_at` — `TEXT`; NOT NULL.


- `approved_by` — `TEXT`; NOT NULL.





### pricing





Initial rows: 4.





Accounting uses SKU-level cost and list price to evaluate discount proposals and margins. Boss makes the final pricing decision; Customer Service drafts the offer.





Fields:





- `sku` — `TEXT`; primary key, no explicit NOT NULL declaration.


- `unit_cost` — `REAL`; NOT NULL.


- `list_price` — `REAL`; NOT NULL.





### tickets





Initial rows: 3.





Boss reads and routes the work queue. All agents use ticket details and references to investigate requests and record progress, outcomes, and drafts on the board.





Fields:





- `id` — `INTEGER`; primary key, no explicit NOT NULL declaration.


- `type` — `TEXT`; NOT NULL.


- `requester` — `TEXT`; NOT NULL.


- `subject` — `TEXT`; NOT NULL.


- `sku` — `TEXT`; nullable.


- `size` — `TEXT`; nullable.


- `qty` — `INTEGER`; nullable.


- `lease_id` — `INTEGER`; nullable.


- `invoice_id` — `INTEGER`; nullable.


- `status` — `TEXT`; NOT NULL.


- `notes` — `TEXT`; nullable.


- `created_at` — `TEXT`; NOT NULL.





Declared foreign key: `tickets.invoice_id` → `invoices.id` (ON UPDATE / ON DELETE: NO ACTION).





Declared foreign key: `tickets.lease_id` → `leases.id` (ON UPDATE / ON DELETE: NO ACTION).





### vendors





Initial rows: 3.





Inventory uses vendor specialties and lead times to identify possible restocking options. Accounting connects vendors to invoices to detect shipping blocks.





Fields:





- `id` — `INTEGER`; primary key, no explicit NOT NULL declaration.


- `name` — `TEXT`; NOT NULL.


- `specialty` — `TEXT`; NOT NULL.


- `lead_days` — `INTEGER`; NOT NULL.





## Relationships and implementation implications





The only declared foreign keys are `tickets.lease_id → leases.id`, `tickets.invoice_id → invoices.id`, and `invoices.vendor_id → vendors.id`.





Logical relationships also connect ticket `(sku, size)` to inventory `(sku, size)`, ticket/inventory `sku` to pricing `sku`, and payments `account` to cash_accounts `name`. These are not enforced by declared foreign keys. `payments.ref_id` is a nullable reference interpreted together with `kind`; its target is not enforced by the schema. Vendor specialties are descriptive text, not a SKU-to-vendor mapping. Agents must validate supplier suitability rather than assume a guaranteed supplier for every SKU.





The schema has no dedicated approvals, purchase orders, customer messages, agent messages, or discount-request amount fields. Future implementation must explicitly choose how to represent these; their existence should not be assumed. No CHECK constraints define statuses, positive quantities, nonnegative balances, or permitted payment kinds. Application tools must enforce shop rules, human approval, and consistent updates.





## Three open tickets





The shop date is **2026-08-31**, from `desk.date_today`. All three tickets currently have status `open`.





### Ticket 101 — Bulldog tee





- Type: `customer_order`; requester: Tauhid Zaman; created: `2026-08-31T09:15:00-04:00`.


- Request: one `CC-TEE-WHITE` in size `S`. Notes: "Needs a tee in size S."


- Inventory has zero small tees in Aisle B, so the shortfall is one. Other sizes cannot satisfy the specified size.


- Pricing gives unit cost $8 and list price $28.


- `invoice_id = 501` links directly to an open $840 invoice due 2026-08-28, three days overdue by the shop clock. Its description is "Rush reprint CC-TEE-WHITE S".


- Invoice 501 links to vendor 1, Bulldog Print Co, whose specialty is apparel reprint and lead time is five days. The unpaid invoice blocks this vendor from shipping.


- Boss coordinates Inventory and Accounting to investigate stock and the shipping block; Accounting prepares human payment approval, and Customer Service drafts an update. Paying the invoice alone does not establish that new stock has arrived. A five-day lead time from the shop date would imply September 5 only if the supplier can start then; no confirmed delivery date is stored.





### Ticket 102 — Rent due





- Type: `rent_notice`; requester: Elm City Properties; created: `2026-08-31T11:05:00-04:00`.


- `lease_id = 1` links to the Chapel Street shop lease with landlord Elm City Properties, monthly rent $2,400, and next due date 2026-09-02.


- The rent is due in two days and is not yet overdue. Ticket notes say: "Email: shop rent due in 2 days."


- Facilities checks the lease and deadline; Accounting checks available cash and prepares human approval. After an approved payment, the working database must record the payment, reduce cash, and update the relevant lease obligation consistently. The schema does not specify the exact rent-cycle advancement policy.





### Ticket 103 — Bulk hoodie discount





- Type: `price_override`; requester: Yale AI Club; created: `2026-08-31T16:55:00-04:00`.


- Request: 20 `CC-HOOD-NAVY` hoodies in size `M`; notes say the student organization is asking for a bulk discount. No specific discount or offered price is stored.


- Inventory has eight medium hoodies in Aisle A, so the shortfall is 12. Quantities in other sizes do not cover the medium-size request.


- Pricing gives unit cost $22 and list price $58. For 20 units, baseline merchandise cost is $440 and undiscounted sales value is $1,160; gross profit before other expenses would be $720, a gross margin of about 62.1%. These are pricing calculations, not incoming cash in this assignment.


- Accounting evaluates proposed discount economics; Inventory investigates restocking and lead times; Boss decides the offer; Customer Service drafts the reply.


- This ticket has no invoice or lease reference. Bulldog Print Co is a possible apparel supplier based on its specialty, but there is no explicit hoodie supplier mapping. If it is selected, its existing unpaid invoice would block shipping.





## Shared cash constraint and future changes





The checking account initially contains $3,400 as of 2026-08-31. Payments is empty. Paying invoice 501 ($840) and rent ($2,400) would consume $3,240 and leave $160 before any restocking costs. This shared cash constraint connects the tickets and requires coordination. Restocking terms, confirmed orders, and additional charges are not stored and must not be invented.





No tickets were resolved and no payments, inventory changes, or other database updates were made during this inspection. Every future mutation must target `data/campus_customs_new.db`. Require human approval for payments, refuse insufficient cash, record completed payments and relevant obligation changes, and keep customer/vendor communications as drafts on the board. Reset the working copy from the original before a full ticket-resolution run.





## Problem 3 — MCP tools





Implemented in `mcp_server/server.py` with FastMCP and the read-only query helper `mcp_server/database.py`. All three tools take no arguments and fetch current rows from `data/campus_customs_new.db`. No original-database access, writes, model calls, approval actions, or fabricated business values occur. Missing related rows are empty lists; missing tickets or database failures raise errors. At the end of Problem 3, the server had not yet been started or connected; Problem 4 subsequently tested stdio MCP.





### `get_ticket_101_tee_order_context`





- **Ticket helped:** 101, Bulldog tee customer order.


- **Tables read:** `tickets` (ticket 101), `inventory` (requested SKU and size), `pricing` (requested SKU), `invoices` (linked invoice and all open invoices for its vendor), `vendors` (linked invoice's vendor), `desk` (shop clock), and `cash_accounts` (available balances).


- **Why useful:** Inventory sees the exact-size stock and vendor lead time; Accounting sees the linked unpaid obligation, other open invoices that could still block shipment, and available cash. Boss and Customer Service can use this evidence to plan the order and draft an update without assuming delivery or payment has occurred.


- **Returned fields:** `ticket`, `inventory`, `pricing`, `linked_invoice`, `linked_vendor`, `vendor_open_invoices`, `desk`, and `cash_accounts`; the ticket is a row object and all other values are lists of full stored rows.





### `get_ticket_102_rent_context`





- **Ticket helped:** 102, Rent due.


- **Tables read:** `tickets` (ticket 102), `leases` (referenced lease), `desk` (shop clock), `cash_accounts` (available balances), and `payments` (full existing ledger).


- **Why useful:** Facilities can compare the actual rent deadline with the shop date; Accounting can examine the rent amount, cash, and payment evidence before requesting human approval. Returning the full ledger avoids inventing a rent-payment convention for `kind` and `ref_id`.


- **Returned fields:** `ticket`, `lease`, `desk`, `cash_accounts`, and `payments`; the ticket is a row object and all other values are lists of full stored rows.





### `get_ticket_103_hoodie_discount_context`





- **Ticket helped:** 103, Bulk hoodie discount.


- **Tables read:** `tickets` (ticket 103), `inventory` (requested SKU and size), `pricing` (requested SKU), `vendors` (full catalog), `invoices` (all open invoices), `desk` (shop clock), and `cash_accounts` (available balances).


- **Why useful:** Accounting gets real cost/list-price inputs for evaluating a proposed discount, while Inventory gets exact-size stock, vendor specialties/lead times, and possible unpaid-invoice shipping blocks. Cash provides the shared budget constraint. The tool does not claim that a catalog vendor supplies hoodies or invent a requested discount.


- **Returned fields:** `ticket`, `inventory`, `pricing`, `vendors`, `open_invoices`, `desk`, and `cash_accounts`; the ticket is a row object and all other values are lists of full stored rows.





The original three tools gather evidence for resolution. Problem 5 adds the guarded operations documented below. See `mcp_server/README.md` for setup and the later stdio launch command.





## Problem 4 — MCP connection and smoke evidence





- Installed FastMCP 4.0.11 in the existing workspace-level `.venv`.


- Saved the homework config in `.mcp.json` and the native Codex configuration in the workspace root's `.codex/config.toml`. Both launch the same server with the workspace venv. Codex CLI confirmed `campus_customs` is enabled.


- `mcp_server/smoke_test.py` connects over actual stdio MCP, discovers the three tools, and calls each with empty arguments. No AI/model API is involved.


- `output/mcp_smoke.json` records each assistant-authored test prompt verbatim, tool name, actual returned output, content blocks, and verification. Every full result exactly matches independently queried rows from `data/campus_customs_new.db`.


- All three tests passed. SHA-256 hashes before and after match for both the original and working databases.


- Reload the coding-assistant session to load the newly saved MCP configuration. The completed smoke test proves the configured server works; it does not claim this existing chat dynamically acquired new tools.





## Problem 5 — Five-agent team





All production roles are PydanticAI agents using **only `gpt-6-luna` through Portkey**, authenticated with `PORTKEY_API_KEY`. Medium reasoning is set and temperature is omitted. No model/provider override is supported. Agent prompts are in `backend/prompts/`, shared Pydantic types in `backend/models.py`, and implementation in `backend/team.py`.





### Roles and connectivity





- **Boss** (`boss.md`): reads the queue, assigns focused work, coordinates shared constraints, decides proposed discounts, and makes final calls. Runtime writes: `record_discount_decision`, `fulfill_ticket_order`, `close_paid_rent_ticket`. Final resolution claims are verified against MCP ticket state.


- **Inventory** (`inventory.md`): checks exact SKU/size quantities and locations, identifies shortfalls, examines vendor specialties/lead times and unpaid invoice blocks, and drafts restock proposals. Runtime write: `draft_purchase_order`.


- **Accounting** (`accounting.md`): checks cash, invoices, rent, payments, costs, and margins across tickets. Prepares pending requests and drafts purchase proposals. Runtime writes: `request_payment`, `draft_purchase_order`. The human HTTP approval route executes payments.


- **Facilities** (`facilities.md`): assesses lease obligations, landlord/space details, and upcoming/overdue rent using the shop clock; delegates payment preparation to Accounting. Own shop access is read-only.


- **Customer Service** (`customer_service.md`): drafts grounded customer/vendor messages and distinguishes proposals from confirmed actions. Runtime write: `save_board_draft`; no sending capability.





Each has `delegate(target, task)` for every other role: **20 directed connections**. Boss is not the sole delegation hub. A role can call any other role, including a parent currently awaiting its report. Only self-delegation and reuse of the same directed edge in the active chain are blocked; depth and delegation limits also bound recursion. Sequential tools, a shared RunUsage, shared limits, and common MCP transport bound the entire tree. Every role must read fresh MCP evidence before returning its typed AgentReport. Reports carry role, ticket_id, outcome, summary, evidence, and next_actions. Unknown facts remain unknown; model reports are not independent database evidence.





### MCP-only data boundary





`backend/mcp_client.py` only transports named MCP calls. Backend agent modules never import SQLite, open database files, or call server database helpers. All shop reads and writes use the MCP server's `data/campus_customs_new.db`. The human-only actions are absent from the agent allowlist, and the normal shop subprocess does not receive the human approval credential. `operations.py` is inside the MCP server, not an agent-side data layer. Database descriptions and notes are untrusted data, not agent instructions.





### Complete MCP tool inventory and database tables








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








### Working-database extension tables





These schemas are created transactionally on the first successful mutation in the **working copy only**. They do not exist in the original shop schema, are implementation additions, and are not invented original shop facts. Read tools return empty lists before creation.





- **approval_requests**: `id INTEGER` primary key; `ticket_id INTEGER` required FK to tickets; `kind TEXT` required (`invoice`, `rent`, `purchase_order`); `ref_id INTEGER` required; `obligation_date TEXT` required; `amount REAL` required and positive; `account TEXT` required; `status TEXT` required (`pending`, `approved`, `rejected`, `paid`); `approved_by TEXT` nullable; `requested_at TEXT` required; `payment_id INTEGER` nullable FK to payments. Unique `(kind, ref_id, obligation_date, account)` prevents duplicate requests for the same terms/account. Accounting uses it to separate proposals from human authorization and completed payments. `kind` determines whether ref_id refers to invoices, leases, or purchase_order_drafts; account is a logical cash_accounts.name reference.


- **board_drafts**: `id INTEGER` primary key; `ticket_id INTEGER` required FK to tickets; `audience TEXT` required (`customer`, `vendor`); `body TEXT` required; `created_at TEXT` required. Unique `(ticket_id, audience, body)` makes identical drafts idempotent. Customer Service stores unsent messages here for the board.


- **purchase_order_drafts**: `id INTEGER` primary key; `ticket_id INTEGER` required FK to tickets; `vendor_id INTEGER` required FK to vendors; `sku TEXT` required; `size TEXT` required; `qty INTEGER` required and positive; `unit_cost REAL` required; `status TEXT` required, default `draft`; `created_at TEXT` required; `confirmed_by TEXT` nullable; `received_qty INTEGER` required, default zero; `funding_invoice_id INTEGER` nullable unique FK to invoices. Unique `(ticket_id, vendor_id, sku, size, qty)`. Inventory/Accounting record draft shortfall proposals; a human attests supplier suitability, real quote, and later physical receipt. Status progresses draft → confirmed → paid → received; a human-attested paid linked invoice can fund the draft directly, avoiding a second purchase charge. Partial receipts keep status paid with received_qty increased. Draft cost is planning data until confirmed, not a real supplier quote.


- **discount_decisions**: `ticket_id INTEGER` primary key FK to tickets; `unit_price REAL` required and positive; `rationale TEXT` required; `decided_at TEXT` required. Boss records a proposed pricing decision without altering global list prices, asserting customer acceptance, or adding revenue.





### Business safety guardrails





- Original database is never modified. Missing working database errors rather than generating an empty fallback. Reads use read-only mode; writes use existing-file mode, foreign-key enforcement, explicit transactions, and write locks.


- `desk.date_today` is the shop date for obligations and stored operation dates. Audit timestamps use real UTC and are explicitly separate from the shop clock. Rent payment advances next_due by one calendar month from the recorded obligation date, clamping month-end days; this is the implemented rent-cycle policy.


- Vendor lead times come from `vendors`. Open unpaid invoices block purchase payment/shipment receipt for that vendor. Supplier specialties alone are not SKU confirmation. Drafts and elapsed lead times cannot create inventory.


- Every outgoing payment derives its amount from an existing invoice, rent obligation, or human-confirmed quote. It needs a stored, named human approval authenticated through the separate local human interface; agents cannot authorize it. Terms are rechecked at execution.


- Decimal validation rejects nonfinite, negative, or fractional-cent money. Cash must be sufficient. A payment, balance decrement, obligation update, and approval status change occur in one transaction; failures roll everything back. No incoming-cash/deposit/revenue tool exists.


- Paid-request replay returns the original payment without debiting cash twice. Already paid or changed obligations are refused, even if multiple approvals or accounts were requested.


- Merchandise fulfillment requires actual sufficient stock for the exact SKU/size, a positive ticket quantity, and for price overrides a recorded decision covering both stored cost and confirmed supplier quotes without exceeding list price. Stock is decremented and ticket status changed atomically. No revenue is recorded.


- Purchase drafts require quantities within the current shortfall; real supplier/quote confirmation is human-only. Separate human payment approval is still required. Physical receipts are human-only, require a paid order and no invoice shipping block, and cannot exceed the unreceived balance. A reprint invoice does not establish receipt quantity by itself. A human may explicitly attest that confirmed goods are covered by the ticket's paid linked invoice; the vendor must match, invoice amount must cover the goods cost, and its funding reference cannot be reused on another order. This avoids charging again for already-funded reprints.


- Rent ticket closure requires a completed approved rent payment for that ticket. Merchandise and rent tickets stay open while approvals, funds, supplier confirmation, or actual stock are missing. Saving a draft is not resolution.


- Customers, vendors, landlords, and banks are never contacted. Draft tools store text only. There is no email, phone, payment-network, or vendor API integration.





### Token, cost, and loop limits





Defaults are validated in `backend/models.py` and enforced in `backend/team.py` across the entire delegation tree, not per agent:





- 24 model requests; 24,000 reported total tokens.


- Estimated 8,000 maximum input tokens per request; provider output cap 1,600 tokens per request, including provider reasoning tokens where counted by the Responses API.


- 60 PydanticAI tool calls and separately 60 MCP calls; 12 delegations; four delegation edges maximum; self-delegation/repeated active edges blocked; tools sequential.


- 30 seconds per model request, no SDK retry; 180 seconds per full team run. Budget/error/cancellation events are audited and surfaced to the caller.


- $1.00 **estimated** application cost ceiling per run, with a full next-request reservation. Paid runs require operator-supplied verified conservative input/output USD-per-million ceilings; no live price is invented. Estimates use reported usage, charge cached input at the full configured ceiling, and do not claim exact provider billing. Missing prices fail closed. A Portkey-side spend cap is needed for a hard billing ceiling.


- Full next-request input/output token reservation is checked before each model request. PydanticAI checks input estimates and accumulated reported tokens. Estimates can differ from actual provider tokenization; response-time limit exceptions remain visible and preserved in audit.


- Overrides use `CAMPUS_` plus the uppercase RunBudget field name within validated bounds. Model/provider, medium reasoning, omitted temperature, MCP-only access, and human approval cannot be switched by budget settings.





### Audit and verification





`output/audit_trail.json` retains existing entries and appends each team/agent start, graph-step start/finish, model messages, MCP call/result/refusal, delegation, failure, final report, and human-action result. Entries carry sequence, run ID, role, and UTC time. File locking and atomic replacement protect concurrent appends. Corrupt/non-array history fails without reset. Secrets are not included in normal logs. Offline test steps are explicitly labeled and use disposable shop copies; they are not production ticket outcomes.





`backend/tests/test_problem5.py` checks all 20 directed delegation edges with deterministic offline protocol responders inside real PydanticAI loops. Business tests call real MCP tools on disposable copies and cover human approvals, replay, insufficient funds/rollback, stale terms, rejection, vendor blocks, quote confirmation, receipts, exact-size fulfillment, discount floors, no revenue, shop dates, and corrupt-audit refusal. Evidence is `output/problem5_checks.json`. No paid Portkey model calls are made by this suite, so live provider integration is not asserted by these results. Production database hashes remain unchanged.





See `backend/README.md` for run commands and human review flow, and `mcp_server/README.md` for current MCP configuration and tool details.








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





### Problem 7 verification





All 3 HTTP integration tests and all 10 existing business/agent regression tests passed. HTTP tests use real in-memory FastMCP tools on disposable copies and a deterministic job runner; regression tests exercise the actual offline PydanticAI team, all delegation edges, and business guardrails. No paid model calls were made. Live Uvicorn startup from backend/ and real stdio MCP reads returned tickets 101/102/103 as open and checking balance 3400. Original and working database SHA-256 hashes both remain 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a. Evidence: output/problem7_checks.json, output/p7_http_checks.log, output/p7_regression.log, and output/p7_live_reads.json.





## Problem 8 — React dashboard





Frontend: frontend/ with React/Vite/TypeScript. Run npm run dev from that directory; port 5173 connects directly to http://localhost:8000. Backend CORS supports both localhost and 127.0.0.1 on 5173.





- GET /dashboard: a current snapshot of tickets, cash_accounts, desk, pending/completed payment and purchase records, and backend-session runs through one read_shop_board MCP call. Used for the ticket queue, stored resolution, cash, human review, and run status.


- GET /activity now also accepts ticket_id and include_test_runs=false: scopes audit entries by ticket-associated run IDs and excludes offline-test teams. Existing run_id, after, and limit parameters remain available.


- POST /tickets/{id}/run, POST /approvals/payments/{id}, and POST /approvals/purchases/{id}: frontend actions use the existing human-safe API contracts. Payment cash updates come from a refreshed MCP snapshot.





The UI renders actual database text safely as React text, presents agent status/contributions and exact MCP tool evidence, and keeps unused roles on standby. Purchase confirmation needs an actual quote and never spends cash. Payments need a named human decision and explicit attestation. Backend failures and last-confirmed stale data remain visible. See output/design.md for layout/accessibility choices and frontend/README.md for setup.





Problem 8 validation: 5 frontend interaction tests and 4 backend integration tests passed; TypeScript and the Vite production build passed. Browser verification confirmed real tickets/cash, ticket selection, and mobile layout without horizontal overflow. Tests used isolated fixtures; no paid AI calls or changes to either shop database. Evidence: output/problem8_checks.json, output/p8_backend_checks.log, output/dashboard-preview.jpg.





## Problem 9 run environment





Reset via POST /reset preserved audit history. Starting checking balance: 3400.00, recorded in output/p9_starting_board.json. Verified pricing and conservative token-rate configuration are recorded in output/p9_price_basis.json. The actual Portkey route reports azure-openai and rejected the Responses input-token-count endpoint on the first run. PortkeyResponsesModel now estimates the complete mapped request locally using o200k_base with a 25% margin plus 256 tokens, keeping preflight limits enabled. Estimates are not exact provider usage: provider-reported input/output tokens remain authoritative after requests and drive cumulative usage/cost checks. The model remains gpt-6-luna through Portkey, medium reasoning, no temperature. No alternate model or key was introduced.





For real final runs, the workspace .env sets CAMPUS_MAX_TOTAL_TOKENS=80000 and CAMPUS_TIMEOUT_SECONDS=480 so shared multi-agent context fits; the existing 24-request, 60-tool, 12-delegation, depth-4, per-request 8000-input/1600-output, and estimated $1-per-run caps remain. All actual consumption and failures remain in audit history.





Final-run request cap was increased to 40 after a genuine 24-request refusal; the shared 80000-token, 480-second and estimated $1 limits stay enforced. Agent prompts clarify automatic report returns and discourage redundant callbacks without removing any delegation edge. Failed attempts remain part of actual evidence.






### Problem 9 actual evidence and remaining human decisions



The reset is recorded at audit sequence 1821. Real dashboard runs were made for all three tickets using gpt-6-luna through Portkey. The audit retains the failed provider preflight, Windows audit-write race, and request-limit attempt as well as subsequent real agent actions. Windows audit replacement now retries transient file contention, and activity reads share the audit lock. Four isolated backend integration tests passed after these runtime fixes (output/p9_runtime_checks.log).



- Ticket 101: Boss, Inventory, and Accounting investigated stock and invoice 501. Accounting prepared pending payment request #1 for $840; Inventory prepared one small white tee as purchase draft #1. The run exhausted its request cap and did not complete a final Boss report. No supplier quote, invoice coverage, stock receipt, payment, or fulfillment has been asserted.

- Ticket 102: Boss contacted Facilities, which delegated to Accounting. Accounting prepared pending rent payment request #2 for $2,400. The completed run returned awaiting_human. It used 10 requests and 17,103 provider-reported tokens, with a conservative estimated model cost of $0.0067325.

- Ticket 103: Boss contacted Inventory first; Inventory delegated financial analysis to Accounting. Boss separately requested an unsent draft from Customer Service. The completed run returned awaiting_human. Boss recorded a proposed $52 unit price, explicitly without customer acceptance, and a customer draft was saved. Exact medium stock remains 8 against a 20-unit request. It used 20 requests and 45,542 provider-reported tokens, with a conservative estimated model cost of $0.0178346. The earlier customer draft predates the Boss's price proposal and therefore states that no price has yet been approved; this historical draft is preserved as actual evidence.



Current cash reconciliation: $3,400.00 starting balance minus $0.00 recorded payments equals $3,400.00, exactly matching cash_accounts in a separate read-only SQLite verification. Original database SHA-256 is unchanged. Expected sections are preserved; their baseline hashes were originally computed using Windows cp1252 decoding, which the verifier accounts for without changing their text. Evidence: output/p9_verification.json and output/resolved_tickets.json.



Human payment approval is still required for the two prepared requests. Paying both would leave $160.00. Twelve additional hoodies at the stored $22 planning cost would require $264.00, a $104.00 deficit; no revenue or artificial cash increase is allowed. A confirmed supplier quote and actual receipt are also needed before asserting tee stock. The human has been asked whether the hoodie request should be declined or remain blocked while a valid supplier/funding alternative is provided. No decision has been inferred from silence.



output/desk_tickets.html now contains real Actual agents, delegations, tools, reports, and current cash while retaining Expected sections. output/resolved_tickets.json explicitly reports complete=false and all stored statuses open. output/resolved_board.html is an evidence page with clearly labeled pending captures; resolved-ticket screenshots will only be embedded after the corresponding database statuses really become resolved. The live dashboard remains available for human review. These files document progress honestly and do not claim that Problem 9 is finished.



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


## Final P9 verification and current budget (2026-10-05)

All three database tickets are resolved: 101 fulfilled using explicitly user-authorized simulated supply evidence; 102 closed after approved rent; 103 declined for insufficient stock/funding, with an unsent customer draft. Checking reconciles exactly: $3,400 - $840 (invoice 501, Ticket 101) - $2,400 (rent, Ticket 102) - $0 (Ticket 103) = $160. Original database and Expected sections are unchanged. Earlier pending-state notes are historical snapshots; resolved_tickets.json and p9_verification.json contain final evidence. The standalone resolved_board.html embeds three real dashboard screenshots. Audit history retains all 2,945 entries, including failures and continuations.

The 8,000-input-token limit was an implementation choice, not a user requirement. Current input allowance is 16,000 per model request, with 80,000 aggregate tokens per run, 40 requests, 1,600 output tokens per request, 60 tool calls, 12 delegations, depth 4, 480 seconds, and a $1 estimated-cost ceiling. These are ceilings, not targets. No paid model rerun was needed for this evidence review. Resolved tickets can use POST /tickets/{ticket_id}/run with review_only=true; every agent mutation is blocked in this mode.
