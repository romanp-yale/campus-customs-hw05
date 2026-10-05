"""Collect final-run evidence from MCP and audit history, never fabricated outcomes."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import html
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.config import load_environment
from backend.mcp_client import ShopMCP
from backend.audit import file_lock
OUT=ROOT/'output'

def esc(value): return html.escape(str(value))
def dollars(value): return '$'+format(Decimal(str(value)),',.2f')

def save(board):
    with file_lock(OUT/'audit_trail.lock'):
        audit=json.loads((OUT/'audit_trail.json').read_text(encoding="utf-8"))
    reset=max(e['sequence'] for e in audit if e['event']=='human_api_action' and e['data'].get('tool')=='reset_working_database')
    events=[e for e in audit if e['sequence']>reset]
    run_tickets={e['run_id']:e['data']['ticket_id'] for e in events if e['event']=='agent_started' and e['data'].get('ticket_id') in (101,102,103)}
    starting=json.loads((OUT/'p9_starting_board.json').read_text(encoding='utf-8-sig'))['board']
    start=Decimal(str(next(a for a in starting['cash_accounts'] if a['name']=='checking')['balance']))
    end=Decimal(str(next(a for a in board['cash_accounts'] if a['name']=='checking')['balance']))
    payments=board['payments']
    total=sum((Decimal(str(p['amount'])) for p in payments if p['account']=='checking'),Decimal(0))
    assert start-total==end, 'Cash ledger does not reconcile exactly.'
    tickets=[]
    for ticket in board['tickets']:
        tid=ticket['id']; ev=[e for e in events if run_tickets.get(e['run_id'])==tid]
        roles=list(dict.fromkeys(e['role'] for e in ev if e['event']=='agent_started'))
        delegations=[{'from':e['role'],'to':e['data']['target'],'task':e['data']['task'],'run_id':e['run_id'],'sequence':e['sequence']} for e in ev if e['event']=='delegation']
        tools=[{'agent':e['role'],'tool':e['data']['tool_name'],'arguments':e['data']['arguments'],'run_id':e['run_id'],'sequence':e['sequence']} for e in ev if e['event']=='mcp_call']
        contributions={r:[e['data']['report'] for e in ev if e['event']=='agent_finished' and e['role']==r] for r in roles}
        approvals=[a for a in board['approval_requests'] if a['ticket_id']==tid]
        payment_ids={a['payment_id'] for a in approvals if a['payment_id'] is not None}
        ledger=[p for p in payments if p['id'] in payment_ids]
        drafts=[p for p in board['purchase_order_drafts'] if p['ticket_id']==tid]
        resolution=next((r for r in board.get('ticket_resolutions',[]) if r['ticket_id']==tid),None)
        supply_evidence=[e for e in board.get('supply_evidence',[]) if e['purchase_order_id'] in {p['id'] for p in drafts}]
        reports=[e['data']['report'] for e in ev if e['event']=='team_finished']
        run_ids=list(dict.fromkeys(e['run_id'] for e in ev))
        runs=[]
        for run in run_ids:
            revents=[e for e in ev if e['run_id']==run]
            final=next((e for e in reversed(revents) if e['event'] in ('team_finished','team_failed','api_run_failed')),None)
            runs.append({'run_id':run,'status':'completed' if final and final['event']=='team_finished' else 'failed' if final else 'in_progress','last_sequence':revents[-1]['sequence'],'error_type':final['data'].get('error_type') if final else None,'usage':next((e['data']['usage'] for e in reversed(revents) if 'usage' in e['data']),None)})
        tickets.append({'ticket_id':tid,'subject':ticket['subject'],'final_status':ticket['status'],'outcome':resolution['outcome'] if resolution else reports[-1]['outcome'] if reports else 'not_completed','resolution_decision':resolution,'supply_evidence':supply_evidence,'final_report':reports[-1] if reports else None,'agents_participated':roles,'delegations':delegations,'mcp_tools_used':tools,'agent_contributions':contributions,'approval_requests':approvals,'human_approvals':[a for a in approvals if a['approved_by'] is not None],'purchase_orders':drafts,'payments':ledger,'checking_change':str(-sum((Decimal(str(p['amount'])) for p in ledger if p['account']=='checking'),Decimal(0))),'runs':runs})
    result={'complete':all(t['final_status']=='resolved' for t in tickets),'generated_at_utc':datetime.now(timezone.utc).isoformat(),'model':'gpt-6-luna','provider':'Portkey','reset_audit_sequence':reset,'starting_checking_balance':str(start),'ending_checking_balance':str(end),'checking_ledger_debits':str(total),'exact_cash_reconciliation':True,'original_database_sha256':hashlib.sha256((ROOT/'data/campus_customs.db').read_bytes()).hexdigest(),'tickets':tickets}
    (OUT/'resolved_tickets.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n', encoding="utf-8")
    (OUT/'p9_final_board.json').write_text(json.dumps(board,indent=2,ensure_ascii=False)+'\n', encoding="utf-8")
    source=(OUT/'desk_tickets.html').read_text(encoding="utf-8")
    expected_before=re.findall(r'<section class="expected".*?</section>',source,re.S)
    for t in tickets:
        tid=t['ticket_id']
        parts=[f'<section class="actual" aria-labelledby="actual-{tid}"><h3 id="actual-{tid}">Actual</h3>',f'<p><strong>Stored status: {esc(t["final_status"])}.</strong> Latest completed team outcome: {esc(t["outcome"])}.</p>',f'<h4>Agents that participated</h4><p>{esc(", ".join(t["agents_participated"]) or "No agents have run this ticket yet.")}</p>']
        parts+=['<h4>Recorded delegations</h4><ul>']+[f'<li><strong>{esc(d["from"])} → {esc(d["to"])}</strong><p>{esc(d["task"])}</p></li>' for d in t['delegations']]+['</ul>']
        parts+=['<h4>MCP tools actually called</h4><ul>']+[f'<li><strong>{esc(role)}</strong>: {esc(", ".join(dict.fromkeys(call["tool"] for call in t["mcp_tools_used"] if call["agent"]==role)) or "No completed tool call recorded.")}</li>' for role in t['agents_participated']]+['</ul>']
        parts+=['<h4>Agent contributions</h4>']
        for role,reports in t['agent_contributions'].items():
            parts.append(f'<p><strong>{esc(role)}</strong>: {esc(reports[-1]["summary"] if reports else "Attempt recorded, but no final AgentReport was completed.")}</p>')
        if t['final_report']:
            parts.append(f'<h4>Final team report</h4><p>{esc(t["final_report"]["summary"])}</p>')
        parts.append('<h4>Human approvals and payments</h4>')
        parts += [f'<p><strong>Supply evidence: {esc(e["source"])}</strong> ({esc(e["kind"])}). {esc(e["note"])} Authorized by {esc(e["approved_by"])}.</p>' for e in board.get('supply_evidence',[]) if e['purchase_order_id'] in {p['id'] for p in t['purchase_orders']}]
        parts += [f'<p>Request #{a["id"]}: {esc(a["kind"])} {dollars(a["amount"])} · {esc(a["status"])} · approver: {esc(a["approved_by"] or "not approved")}</p>' for a in t['approval_requests']]
        if not t['human_approvals']: parts.append('<p>No human payment approval recorded.</p>')
        parts.append(f'<p>Checking change attributed to this ticket: <strong>{dollars(t["checking_change"])}</strong>.</p>')
        parts.append('<p class="finish"><strong>Comparison:</strong> Expected sections remain unchanged. Actual evidence includes every real attempt after reset, including provider/audit failures and subsequent continuations. Human payment execution uses the P7 approval route, superseding the earlier Expected execution plan.</p>')
        parts.append('</section>')
        source=re.sub(fr'<section class="actual" aria-labelledby="actual-{tid}">.*?</section>',lambda _:''.join(parts),source,flags=re.S)
    cash=['<section id="cash" role="tabpanel" aria-labelledby="tab-cash" tabindex="0" hidden><div class="coming"><h2>Cash</h2>',f'<p>Starting checking balance: <strong>{dollars(start)}</strong></p>']
    for t in tickets:
        cash.append(f'<h3>Ticket {t["ticket_id"]}: {dollars(t["checking_change"])}</h3>')
        cash += [f'<p>Payment #{p["id"]} · {esc(p["kind"])} reference {p["ref_id"]} · {dollars(p["amount"])} paid from {esc(p["account"])} · approved by {esc(p["approved_by"])}</p>' for p in t['payments']]
        if not t['payments']:cash.append('<p>No cash payment recorded for this ticket.</p>')
    cash += [f'<p>Ending checking balance: <strong>{dollars(end)}</strong></p>',f'<p>Exact ledger reconciliation: {dollars(start)} − {dollars(total)} = {dollars(end)}. Matches the checking row returned by MCP. No incoming revenue is modeled.</p>','<p>'+('All three tickets are resolved.' if result['complete'] else 'Final runs are still in progress or blocked. These are current actual values, not a claim of completion.')+'</p></div></section>']
    source=re.sub(r'<section id="cash".*?</section>',lambda _:''.join(cash),source,flags=re.S)
    assert expected_before==re.findall(r'<section class="expected".*?</section>',source,re.S)
    (OUT/'desk_tickets.html').write_text(source, encoding="utf-8")
    print(json.dumps({'complete':result['complete'],'statuses':[(t['ticket_id'],t['final_status'],t['outcome']) for t in tickets],'starting':str(start),'ending':str(end),'audit_entries':len(audit)},indent=2))

async def main():
    load_environment()
    async with ShopMCP() as shop:
        board=await shop.call('read_shop_board',{})
    save(board)

if __name__=='__main__': asyncio.run(main())
