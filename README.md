# Campus Customs Multi-Agent Operations

Completed homework 5: a FastMCP SQLite server, five fully connected PydanticAI agents, FastAPI backend, and React/Vite/TypeScript operations dashboard. All production agents use **gpt-6-luna through Portkey**. Shop facts come exclusively through MCP.

## Included submission

`data/campus_customs.db` is the untouched supplied database. `data/campus_customs_new.db` contains the finished run. `backend/prompts/` contains Boss, Inventory, Accounting, Facilities, and Customer Service prompts. `AI_prompts.md` preserves assignment and run prompts verbatim. `output/` contains the harness, smoke results, design notes, Expected/Actual/Cash/Reflection report, resolved JSON, embedded screenshot board, audit trail, verification and GitHub URL.

Final checking: **$3,400 - $840 invoice - $2,400 rent = $160**. All three tickets are resolved. Ticket 101 used explicitly user-authorized simulated quote, invoice coverage and receipt; these are not verified supplier/physical facts. Ticket 103 was declined for insufficient stock/funding, not fulfilled. Both payments were explicitly human approved. Drafts were never sent. Earlier failed attempts remain in the audit.

## Install and configure

Use Python 3.13 and Node.js 20.19+ or 22.12+. From the repository root (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
cd frontend
npm ci
cd ..
```

Edit the ignored `.env`: set `PORTKEY_API_KEY` and verified conservative input/output USD-per-million price ceilings for your Portkey route. Never commit keys. The backend generates a local human-only credential if `CAMPUS_HUMAN_APPROVAL_KEY` is empty; you may set your own local value. No OPENAI_API_KEY is required. Default run ceilings are 16,000 input tokens per request, 80,000 aggregate tokens, 40 requests, 1,600 output tokens per request, $1 estimated cost, and 480 seconds. Price ceilings are user configuration, not assumed live pricing.

## 1. Reset the working database

For a clean run, reset only when no ticket is running. The original is never changed. With the backend running, reset through its human route so the action is appended to the audit:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/reset -ContentType application/json -Body '{"approved_by":"Your name","confirm":true}'
Invoke-RestMethod http://localhost:8000/cash
```

Checking should return $3,400 and all three tickets should be open. If the backend is stopped, an offline reset is `Copy-Item data/campus_customs.db data/campus_customs_new.db -Force`; use the API for recorded final runs. Reset replaces working shop state, not audit history. Preserve the included final evidence before generating a different run.

## 2. Start the MCP server

Activate the repository venv and run from the root:

```powershell
python mcp_server/server.py
```

This is a stdio server, so it waits for an MCP client rather than displaying an HTTP page. `.mcp.json` uses portable relative paths; launch your coding assistant from the repository root with its venv activated and load that MCP configuration. The backend starts its own stdio MCP subprocess using its active Python interpreter; no separate server terminal is required for the dashboard. See `mcp_server/README.md` for all 17 tools.

## 3. Start FastAPI

In a terminal with the repository venv activated:

```powershell
cd backend
uvicorn main:app --reload --port 8000
```

API documentation: http://localhost:8000/docs. Routes cover ticket status, selected-ticket runs, activity, approvals, checking and reset. Agents prepare obligations; only the guarded human payment API spends cash. Purchase confirmation and stock receipt do not independently spend cash. CORS permits http://localhost:5173.

## 4. Start React

In another terminal:

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173. Select a ticket, run the team, inspect activity/tool evidence and contributions, and approve only the intended payment or purchase. Checking refreshes from the database. Failures and awaiting-human results remain visible. Resolved tickets can be reviewed without allowing agent mutations.

## 5. Perform a clean three-ticket run

1. Start both services, reset through the API above, and record the $3,400 starting checking balance.
2. Select Ticket 101 and run the team. Inspect the stock shortage and invoice request; approve invoice 501 for $840 only if intended. Confirm a valid supplier quote and receipt before fulfillment. Do not invent these facts. To reproduce the included assignment simulation, explicitly authorize and label its $8 quote, invoice coverage and one-tee receipt in the human forms' simulation notes; it causes no second cash charge.
3. Select Ticket 102, run the team and approve the $2,400 rent request. Continue after approval so Boss verifies paid evidence and closes the notice. Checking becomes $160.
4. Select Ticket 103, run its Inventory-first feasibility check. Eight medium hoodies cannot fill twenty; twelve more have a $264 stored planning cost, exceeding $160 cash. To reproduce the included outcome, explicitly direct a decline with an unsent customer explanation. No cash or stock changes should result.
5. Continue awaiting-human runs with specific instructions after supplying the required approvals/evidence. Confirm stored statuses, not merely a model's claim. If a run fails after a committed action, inspect current state and use read-only review rather than repeat the action.
6. Compare Expected with Actual, record each cash change, and verify ending checking against `/cash`. The included completed artifacts show the submitted run; a new run may differ. Preserve audit history and update output evidence from real runs rather than replacing it with invented results.

## Verification

```powershell
python -X utf8 -m unittest discover -s backend/tests -v
cd frontend
npm test
npm run build
```

Tests use disposable databases and audit files. The final review passed 17 backend/business/agent tests and six frontend tests plus the production build. See `output/p10_final_review.md`. Shop safeguards include the stored shop clock, vendor lead times, unpaid-invoice shipping blocks, named human approval, no negative cash, no incoming revenue and no external customer/vendor contact.

The public repository URL is in `output/github_url.txt`. `.env`, dependencies, caches, locks and transient database journals are excluded; both required databases and all source/submission outputs are included.
