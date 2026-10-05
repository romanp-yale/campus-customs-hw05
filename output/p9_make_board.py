"""Build the screenshot evidence page only from verified resolved states."""
from pathlib import Path
import base64
import html
import json

OUT=Path(__file__).resolve().parent
result=json.loads((OUT/'resolved_tickets.json').read_text(encoding='utf-8'))
escape=lambda value:html.escape(str(value))
sections=[]
for ticket in result['tickets']:
    tid=ticket['ticket_id']; shot=OUT/f'resolved_ticket_{tid}.jpg'
    verified=ticket['final_status']=='resolved' and shot.exists()
    section=f'<article><div class="heading"><h2>Ticket {tid} · {escape(ticket["subject"])}</h2><span>{escape(ticket["final_status"])}</span></div>'
    if verified:
        encoded=base64.b64encode(shot.read_bytes()).decode('ascii')
        section+=f'<figure><img src="data:image/jpeg;base64,{encoded}" alt="Real dashboard screenshot showing Ticket {tid} resolved"/><figcaption>Captured from the live React dashboard after the stored ticket status was verified resolved.</figcaption></figure>'
    else:
        section+='<div class="pending"><p>A resolved-ticket screenshot is not available yet. No screenshot or successful outcome has been fabricated.</p></div>'
    section+='</article>';sections.append(section)
complete=result['complete'] and all((OUT/f'resolved_ticket_{t["ticket_id"]}.jpg').exists() for t in result['tickets'])
status='All three tickets resolved' if complete else 'Evidence in progress — human decisions or unresolved tickets remain'
page='''<!doctype html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>Campus Customs · Resolved board evidence</title><style>body{margin:0;background:#0b111a;color:#dce7ee;font:15px system-ui,sans-serif}main{max-width:1250px;margin:auto;padding:38px 22px}h1{font-size:30px;letter-spacing:-1px}header p,figcaption{color:#8fa5b7;line-height:1.8}.heading{display:flex;align-items:center;justify-content:space-between;gap:15px}.heading span{color:#82e6c0;border:1px solid #82e6c035;border-radius:6px;padding:5px 10px;font-size:12px}article{background:#142130a6;border:1px solid #a6bbd01f;border-radius:12px;margin:25px 0;padding:20px}h2{font-size:19px}figure{margin:14px 0 0}img{display:block;width:100%;height:auto;border-radius:8px}figcaption{font-size:12px;margin-top:10px}.pending{border:1px dashed #50657c;border-radius:8px;padding:28px;margin:12px 0;color:#9bafbf}a{color:#82e6c0}.status{color:#e7bc74}footer{color:#7f97ab;font-size:12px;margin-top:25px}</style></head><body><main><header><p>CAMPUS CUSTOMS / PROBLEM 9</p><h1>Resolved board evidence</h1><p class="status">'''+escape(status)+'''</p><p>Stored status and actual dashboard captures. Original database preserved; Expected workflows remain in <a href="desk_tickets.html">the ticket comparison page</a>. Structured evidence: <a href="resolved_tickets.json">resolved_tickets.json</a>.</p></header>'''+''.join(sections)+f'<footer>Current checking balance: ${float(result["ending_checking_balance"]):,.2f}. Audit history is append-only. Generated {escape(result["generated_at_utc"])}.</footer></main></body></html>'
(OUT/'resolved_board.html').write_text(page,encoding='utf-8')
print('Resolved screenshot evidence complete:',complete)
