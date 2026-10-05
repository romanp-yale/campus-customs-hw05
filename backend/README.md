# Campus Customs five-agent team



`team.py` builds Boss, Inventory, Accounting, Facilities, and Customer Service with PydanticAI. Every production agent uses the same fixed `gpt-6-luna` Responses model through `https://api.portkey.ai/v1`, authenticated only with `PORTKEY_API_KEY`. Reasoning is medium, no temperature is set, and SDK retries are disabled to avoid hidden retry costs.



Prompts live in `prompts/`, one Markdown file per role. Shared types are in `models.py`. `mcp_client.py` is an MCP transport adapter, not a database layer: agents never import SQLite, open database files, or call server helpers directly. They access shop facts and mutations using `shop_tool`, which calls the configured MCP subprocess. A runtime allowlist restricts writes by role. All five have `delegate(target, task)` for every other role; self-delegation, repeated active directed edges, excess nesting, and delegation overruns are blocked. A specialist can call back to Boss for a focused decision even while Boss is awaiting its report. Delegates share the same PydanticAI RunUsage and UsageLimits object semantics across the run.



## Local setup



From the workspace root, reuse the existing venv:



```powershell

.\.venv\Scripts\python.exe -m pip install -r homework/hw-05/backend/requirements.txt

```



Configure environment variables or an ignored `.env` in `homework/hw-05` or the workspace root. Existing environment values take precedence. See `../.env.example`.



- `PORTKEY_API_KEY`: your Portkey credential.

- `CAMPUS_INPUT_USD_PER_MILLION` and `CAMPUS_OUTPUT_USD_PER_MILLION`: verified conservative price ceilings for your actual Portkey route, in USD per million tokens. No live prices are assumed. Paid runs refuse to start until both are supplied.

- `CAMPUS_HUMAN_APPROVAL_KEY`: a separate private local human-action credential. It is not sent to the model or exposed in agent tools. Only configure it when using the human command path.



From `homework/hw-05`:



```powershell

..\..\.venv\Scripts\python.exe -m backend run "Investigate ticket 101 and prepare safe next steps; stop for human approval or missing facts." --ticket 101

```



Omit `--ticket` to coordinate all open tickets. Each report identifies the role, ticket, outcome, evidence, and next actions. Every agent must read MCP evidence before returning a report. A final Boss claim of resolution is checked against actual ticket statuses through MCP. Errors and limits propagate visibly to the CLI and remain in the audit trail. The FastAPI dashboard endpoints are documented below.



## Human approval and physical receipt



Agents create pending payment requests. To review one, from `homework/hw-05` run:



```powershell

..\..\.venv\Scripts\python.exe -m backend approve-payment 1 --name "Your name"

```



The command shows the exact stored request and requires you to type `APPROVE` or `REJECT`. It records authorization through a human-only MCP tool. It does not execute payment. Payment execution belongs exclusively to the HTTP payment approval route; agents cannot execute payments. For the dashboard, approve pending requests through that route rather than this legacy authorization-only command. Amounts come from the database, never from model-supplied payment amounts.



Restock drafts require actual human supplier and quote confirmation before purchase payment:



```powershell

..\..\.venv\Scripts\python.exe -m backend confirm-purchase 1 --unit-cost 8.00 --name "Your name"

```



The numeric arguments above are command-format examples, not assertions about a real supplier quote. Review the displayed record and supply the actual quote. After separate human payment approval and payment, attest physically received stock with:



```powershell

..\..\.venv\Scripts\python.exe -m backend receive-purchase 1 --qty 1 --name "Your name"

```



If the goods are already funded by the ticket's paid linked invoice (such as a reprint), add `--covered-by-paid-invoice` to `confirm-purchase` and explicitly attest that coverage. This uses a matching, paid invoice rather than creating a second purchase payment. The cost must fit within that invoice and the funding reference is unique. Actual receipt still requires separate human attestation.



Both commands require explicit typed confirmation plus the private human credential. Agents cannot access either tool. Receiving cannot exceed the remaining paid quantity and cannot occur while the vendor has an unpaid invoice. There is no external communication or banking integration; all changes are in the assignment's working database. Lead-time passage alone never creates stock. A rush-reprint invoice does not contain a reliable purchase quantity or receipt, so paying it does not automatically restock anything.



## Limits and audit



Default limits apply to the whole delegation tree: 24 model requests, 24,000 total tokens, an estimated 8,000 input tokens per request, 1,600 maximum output tokens per request, 60 PydanticAI tool calls, 60 MCP calls, 12 delegations, four delegation edges of nesting, 30 seconds per model request, and 180 seconds for a team run. Tools and delegations run sequentially. A full next-request token reservation is checked before each request, and PydanticAI checks input estimates and reported usage. Estimators and provider accounting may differ; token failures can be observed after a response. The model output cap is passed to Portkey.



The default estimated USD ceiling is $1.00 per team run. Before a request, the implementation reserves its full input/output ceiling at the configured price ceilings; after a request it uses reported input/output tokens to update the estimate. Rates are operator supplied; taxes, gateway fees, provider differences, and billing reconciliation are not modeled. This is an application estimate, not a guaranteed invoice cap. Set a matching hard spend cap on the Portkey key for provider-side billing enforcement. Missing rates fail closed. Cached inputs are conservatively charged at the full configured input ceiling; no discount is assumed.



Every RunBudget field can be overridden with its uppercase `CAMPUS_` name, for example `CAMPUS_MAX_REQUESTS`, within validated bounds. Model identity, provider endpoint, reasoning, and approval restrictions cannot be overridden by these settings.



`output/audit_trail.json` is a JSON array. A file lock serializes appends; atomic replacement preserves every previous entry and adds only the new entry. Corrupt or non-array history causes failure rather than reset. Entries record UTC timestamps, sequence, run ID, role, model/limits, every graph step start/finish, model messages, MCP calls/results/refusals, delegations, failures, and final reports. Human action results are logged without their secret. Entries from offline verification are explicitly labeled as disposable-fixture tests and are not claims about production ticket progress.



## Verification



From the workspace root:



```powershell

.\.venv\Scripts\python.exe homework/hw-05/backend/tests/test_problem5.py

```



Offline deterministic protocol responders exercise real PydanticAI loops and MCP tools on disposable database copies. They make no AI/provider calls. Tests cover all 20 directed delegation edges, retained audit history, human-only tool isolation, payment approvals, replay protection, insufficient cash/atomic rollback, stale approval, rejection, invoice shipping blocks, supplier confirmation, physical receipt, exact-size fulfillment, discount cost floor, no incoming cash, shop-date use, and corrupt audit refusal. Evidence is saved in `output/problem5_checks.json`. Both production database hashes are checked before and after.



Implementation follows PydanticAI's [delegation with shared usage](https://ai.pydantic.dev/multi-agent-applications/) and [graph iteration](https://ai.pydantic.dev/agents/) patterns. Live Portkey requests are not part of these offline tests.





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


## Final P9 verification and current budget (2026-10-05)

All three database tickets are resolved: 101 fulfilled using explicitly user-authorized simulated supply evidence; 102 closed after approved rent; 103 declined for insufficient stock/funding, with an unsent customer draft. Checking reconciles exactly: $3,400 - $840 (invoice 501, Ticket 101) - $2,400 (rent, Ticket 102) - $0 (Ticket 103) = $160. Original database and Expected sections are unchanged. Earlier pending-state notes are historical snapshots; resolved_tickets.json and p9_verification.json contain final evidence. The standalone resolved_board.html embeds three real dashboard screenshots. Audit history retains all 2,945 entries, including failures and continuations.

The 8,000-input-token limit was an implementation choice, not a user requirement. Current input allowance is 16,000 per model request, with 80,000 aggregate tokens per run, 40 requests, 1,600 output tokens per request, 60 tool calls, 12 delegations, depth 4, 480 seconds, and a $1 estimated-cost ceiling. These are ceilings, not targets. No paid model rerun was needed for this evidence review. Resolved tickets can use POST /tickets/{ticket_id}/run with review_only=true; every agent mutation is blocked in this mode.
