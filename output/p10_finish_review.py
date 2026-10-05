"""Finish requirement review documentation without altering recorded runs."""
from pathlib import Path
import json
import re
from datetime import datetime, timezone

root = Path(__file__).resolve().parent.parent
addition = 'Price/draft sequencing: for a price-override ticket, record your proposed price with record_discount_decision before asking Customer Service to draft the offer. Ask Customer Service to read the stored decision through read_shop_board. If fulfillment is blocked, the draft must describe that proposal and the blockers without claiming acceptance or delivery.'
prompts = root / 'AI_prompts.md'
with prompts.open('a', encoding='utf-8') as f:
    f.write('\n### P10 verification — assistant-authored Boss instruction amendment\n\nThe actual hoodie run saved the draft before its price proposal; this amendment makes the intended order explicit for future runs.\n\n```text\n' + addition + '\n```\n')

for name in ['backend/README.md', 'mcp_server/README.md', 'output/harness.md']:
    p = root / name
    raw = p.read_bytes().decode('utf-8', errors='surrogateescape')
    text = ''.join(bytes([ord(c)-0xdc00]).decode('cp1252') if 0xdc80 <= ord(c) <= 0xdcff else c for c in raw)
    text = text.replace('Actual stock receipt remains a separate human CLI attestation.', 'Actual stock receipt can now be attested through the dashboard receipt control or the human CLI.')
    text = text.replace('FastMCP 4.0.11 exposes fourteen tools: eleven available to application agents (with additional role restrictions) and three human-only actions.', 'FastMCP 4.0.11 exposes sixteen tools: ten available to application agents (with additional role restrictions) and six human-only actions, including the legacy credential-protected payment executor.')
    text += '''

### P10 verification fixes

- POST /approvals/purchases/{purchase_order_id}/receive: named human plus received_qty and explicit confirm=true. Calls the existing human-only receive_purchase_order MCP tool. Requires a paid order, no unpaid supplier invoice, and a positive integer quantity within its remaining units. Receipt changes inventory, never cash. Actual quote and receipt must come from the human, never an agent guess.
- Dashboard: paid, unreceived orders show an actual-receipt form with quantity limits and an explicit physical-verification attestation. After recording, rerun the ticket for guarded fulfillment.
- Agent tool instructions now specify that all four reads take arguments={} and that save_board_draft requires audience customer/vendor and a nonempty body. Selected-ticket runs cannot write another ticket. Boss's prompt records a proposed price before requesting the offer draft.
- Historical run evidence and Expected plans stay unchanged. Prompt amendments affect future runs; they are not evidence that prior failures or unfinished tickets were resolved.

See output/verification.md for the requirement-by-requirement result and output/p10_verification.json for machine-readable evidence.
'''
    p.write_text(text, encoding='utf-8')

page = root / 'output/desk_tickets.html'
text = page.read_text(encoding='utf-8')
preserved = re.findall(r'<section class="(?:expected|actual)".*?</section>|<section id="cash".*?</section>', text, re.S)
text = text.replace('<title>Campus Customs — Expected ticket workflows</title>', '<title>Campus Customs — Ticket evidence and reflection</title>')
text = text.replace('CAMPUS CUSTOMS · PROBLEM 6', 'CAMPUS CUSTOMS · PROBLEMS 6–10')
text = text.replace('<h1>Expected ticket workflows</h1>', '<h1>Ticket evidence and reflection</h1>')
text = text.replace('Actual run evidence will be added later.', 'Actual run evidence, current cash reconciliation, and reflection are now recorded below; unfinished tickets are labeled honestly.')
text = text.replace('This page is a standalone planning document.', 'This standalone report retains the original planning baseline alongside actual evidence.')
text = text.replace('<span class="label">Planning only</span>', '<span class="label">Expected + Actual</span>')
assert preserved == re.findall(r'<section class="(?:expected|actual)".*?</section>|<section id="cash".*?</section>', text, re.S)
page.write_text(text, encoding='utf-8')

checks = {
 'verified_at_utc':datetime.now(timezone.utc).isoformat(),
 'paid_model_calls_during_review':0,
 'business_and_agent_tests':{'passed':True,'count':10,'evidence':'problem5_checks.json'},
 'backend_tests':{'passed':True,'count':5,'evidence':'p10_backend_checks.log'},
 'frontend_tests':{'passed':True,'count':6,'evidence':'p10_frontend_checks.log'},
 'typescript_and_production_build':{'passed':True,'evidence':'p10_frontend_build.log'},
 'mcp_context_smoke':{'passed':True,'count':3,'evidence':'mcp_smoke.json'},
 'original_database_preserved':True,
 'actual_shop_balance':3400,
 'all_tickets_resolved':False,
 'remaining_blockers':['Human approval of invoice $840 and rent $2400','Human tee supplier quote, invoice coverage, and physical receipt','Hoodie shortage of 12; $264 planning cost exceeds projected $160 cash by $104','Resolved dashboard screenshots cannot exist until tickets actually resolve'],
 'fixes':['Dashboard and API for human stock receipt','Exact read/draft MCP argument instructions','Assigned-ticket write guard','Boss price-before-draft instruction','Current tool counts, receipt docs, and report header','UTF-8 repair of mixed-encoded source/docs'],
 'historical_evidence_changed':False,
}
(root / 'output/p10_verification.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
