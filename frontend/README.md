# Campus Customs dashboard

React, Vite, and TypeScript dashboard backed by the real Campus Customs FastAPI/MCP working database. No fabricated live shop values or frontend secrets.

From `homework/hw-05/frontend`:

```powershell
npm install
npm run dev
```

Open http://localhost:5173. Vite binds locally on port 5173 and refuses a busy port. Start the backend in a second terminal with the workspace virtual environment activated:

```powershell
cd ../backend
uvicorn main:app --reload --port 8000
```

The frontend defaults to `http://localhost:8000`. Optional local `.env`: `VITE_API_URL=http://localhost:8000`. Never put PORTKEY_API_KEY or the human MCP credential in a VITE_ variable. The backend loads its own ignored environment setup. Paid agent runs also require the verified input/output price ceilings already documented in backend/README.md; configuration failures appear in the dashboard.

Select a ticket, optionally add run instructions, and click Run ticket. Watch live activity and tool evidence. Expand agent contributions after reports arrive. Human-review controls list pending payments and purchase drafts across all tickets. Review exact payment terms, enter your name, and explicitly attest before approval. Purchase confirmation requires a real quote and does not spend cash. After the awaiting-human run finishes, approve and rerun the ticket to continue. Stock receipt uses the existing human CLI attestation.

```powershell
npm run build
npm test
```

The tests use clearly isolated API fixtures to verify selection, failures, cash refresh, quote/approval requirements, live evidence, contributions, and stored resolution status. They never change the shop database or call a paid model. Design decisions: `../output/design.md`. Runtime API data: `/dashboard`; incremental audit evidence: `/activity`. The original database and historical audit entries remain preserved.
