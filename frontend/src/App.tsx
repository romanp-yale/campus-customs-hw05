import { useState } from 'react';
import { Activity, ArrowDownRight, ArrowRight, Boxes, Check, CheckCircle2, ChevronRight, CircleDollarSign, Clock3, Code2, FileCheck2, Landmark, LayoutDashboard, Loader2, MessageSquare, PackageCheck, Play, Radio, RefreshCw, ShieldCheck, Shirt, Sparkles, Users, Wrench, X } from 'lucide-react';
import { API, money, post } from './api';
import type { Entry, Job, Payment, Purchase, Report, Role } from './api';
import { useDesk } from './useDesk';

const ROLES: { role: Role; initials: string; purpose: string; icon: typeof Users; color: string }[] = [
  { role: 'Boss', initials: 'BO', purpose: 'Direction & decisions', icon: Sparkles, color: 'mint' },
  { role: 'Inventory', initials: 'IN', purpose: 'Stock & suppliers', icon: Boxes, color: 'blue' },
  { role: 'Accounting', initials: 'AC', purpose: 'Cash & margins', icon: CircleDollarSign, color: 'amber' },
  { role: 'Facilities', initials: 'FA', purpose: 'Space & rent', icon: Landmark, color: 'violet' },
  { role: 'Customer Service', initials: 'CS', purpose: 'Customer drafts', icon: MessageSquare, color: 'rose' },
];
const ticketLabel = (type: string) => ({ customer_order: 'Customer order', rent_notice: 'Rent notice', price_override: 'Price override' }[type] || type.replaceAll('_', ' '));
const text = (value: unknown) => typeof value === 'string' ? value : '';
function describe(entry: Entry) {
  const d = entry.data;
  if (entry.event === 'delegation') return `Delegated to ${text(d.target)} · ${text(d.task)}`;
  if (entry.event === 'mcp_call') return text(d.tool_name);
  if (entry.event === 'mcp_result') return `${text(d.tool_name)} returned database evidence`;
  if (entry.event === 'mcp_error') return `${text(d.tool_name)} · ${text(d.error) || text(d.error_type)}`;
  if (entry.event === 'agent_finished') return text((d.report as Report | undefined)?.summary);
  if (entry.event === 'agent_started') return 'Started investigating the ticket';
  if (entry.event === 'team_finished') return 'Team run complete';
  if (entry.event.includes('failed')) return `Run stopped · ${text(d.error_type)}`;
  if (entry.event === 'loop_step_finished') {
    const messages = d.messages as { parts?: { part_kind?: string; content?: unknown }[] }[] | undefined;
    const content = messages?.flatMap(m => m.parts || []).filter(p => p.part_kind === 'text').map(p => text(p.content)).filter(Boolean).join('\n');
    return content || '';
  }
  return '';
}

function Approval({ item, kind, busy, onDecide }: { item: Payment | Purchase; kind: 'payment' | 'purchase'; busy: boolean; onDecide: (kind: string, id: number, body: unknown) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [quote, setQuote] = useState('');
  const [covered, setCovered] = useState(false);
  const [simulationNote, setSimulationNote] = useState('');
  const [attest, setAttest] = useState(false);
  const payment = kind === 'payment' ? item as Payment : null;
  const purchase = kind === 'purchase' ? item as Purchase : null;
  const cost = Number(quote);
  const valid = !!name.trim() && attest && (!purchase || (quote.trim() !== '' && Number.isFinite(cost) && cost > 0 && Math.abs(cost * 100 - Math.round(cost * 100)) < .000001));
  return <article className="approval-card">
    <div className="approval-top"><span className="eyebrow">TICKET {item.ticket_id} / {payment ? 'PAYMENT' : 'PURCHASE'}</span><span className="badge amber">Needs review</span></div>
    <h4>{payment ? `${payment.kind.replaceAll('_', ' ')} · ref ${payment.ref_id}` : `${purchase!.qty} × ${purchase!.sku}`}</h4>
    <div className="approval-amount">{money(payment ? payment.amount : purchase!.qty * purchase!.unit_cost)}<span>{payment ? `from ${payment.account}` : 'planning estimate'}</span></div>
    <p className="muted small">{payment ? `Obligation date ${payment.obligation_date}. Approval records the payment and deducts cash.` : `Vendor #${purchase!.vendor_id} · size ${purchase!.size}. Confirm the actual supplier and quote first.`}</p>
    {!open ? <button className="button secondary full" onClick={() => setOpen(true)} disabled={busy}>Review {kind}<ArrowRight size={15}/></button> : <div className="approval-form">
      <label>Your name<input value={name} onChange={e => setName(e.target.value)} autoComplete="name" placeholder="Human approver" /></label>
      {purchase && <><label>Actual quoted unit cost ($)<input type="number" min="0.01" step="0.01" value={quote} onChange={e => setQuote(e.target.value)} placeholder="Enter the real quote" /></label><label>Simulation note (only if explicitly authorized)<input value={simulationNote} maxLength={1000} onChange={e => setSimulationNote(e.target.value)} placeholder="Leave blank for a verified supplier quote" /></label><label className="checkbox"><input type="checkbox" checked={covered} onChange={e => setCovered(e.target.checked)}/>These goods are covered by the ticket’s paid linked invoice.</label></>}
      <label className="checkbox"><input type="checkbox" checked={attest} onChange={e => setAttest(e.target.checked)}/>{payment ? `I approve this ${money(payment.amount)} payment.` : simulationNote.trim() ? 'I authorize this clearly labeled simulated supplier and quote.' : 'I verified this supplier and actual quote.'}</label>
      <div className="button-row"><button className="button primary" disabled={busy || !valid} onClick={() => void onDecide(kind, item.id, { approved: true, approved_by: name.trim(), ...(purchase ? { confirmed_unit_cost: cost, covered_by_paid_invoice: covered, ...(simulationNote.trim() ? {simulation_note:simulationNote.trim()} : {}) } : {}) })}><Check size={15}/>{payment ? 'Approve & pay' : 'Confirm purchase'}</button>{payment && <button className="button danger" disabled={busy || !name.trim()} onClick={() => void onDecide(kind, item.id, { approved: false, approved_by: name.trim() })}>Reject</button>}<button className="icon-button" aria-label="Close approval review" onClick={() => setOpen(false)}><X size={16}/></button></div>
    </div>}
  </article>;
}

function Receipt({ item, busy, onReceive }: { item: Purchase; busy: boolean; onReceive: (kind: string, id: number, body: unknown) => Promise<void> }) {
  const [name, setName] = useState('');
  const [quantity, setQuantity] = useState('');
  const [simulationNote, setSimulationNote] = useState('');
  const [attest, setAttest] = useState(false);
  const remaining = item.qty - (item.received_qty || 0);
  const qty = Number(quantity);
  const valid = name.trim() && attest && quantity !== '' && Number.isInteger(qty) && qty > 0 && qty <= remaining;
  return <article className="approval-card">
    <div className="approval-top"><span className="eyebrow">TICKET {item.ticket_id} / STOCK RECEIPT</span><span className="badge amber">Human confirmation</span></div>
    <h4>{item.sku} · size {item.size}</h4>
    <p className="muted small">Paid order #{item.id}. {remaining} units remain unreceived. Record only goods physically received; a payment or lead time is not a receipt.</p>
    <div className="approval-form"><label>Your name<input value={name} onChange={e => setName(e.target.value)} placeholder="Human receiver" /></label>
      <label>Quantity actually received<input type="number" min="1" max={remaining} step="1" value={quantity} onChange={e => setQuantity(e.target.value)} /></label>
      <label>Simulation note (only if explicitly authorized)<input value={simulationNote} maxLength={1000} onChange={e => setSimulationNote(e.target.value)} placeholder="Leave blank for a physically verified receipt" /></label>
      <label className="checkbox"><input type="checkbox" checked={attest} onChange={e => setAttest(e.target.checked)} />{simulationNote.trim() ? 'I authorize this clearly labeled simulated receipt for the assignment.' : 'I physically verified these exact SKU/size units.'}</label>
      <button className="button primary" disabled={busy || !valid} onClick={() => void onReceive('receipt', item.id, { approved_by:name.trim(), received_qty:qty, confirm:true, ...(simulationNote.trim() ? {simulation_note:simulationNote.trim()} : {}) })}><PackageCheck size={15}/>{simulationNote.trim() ? 'Record simulated receipt' : 'Record actual receipt'}</button>
    </div>
  </article>;
}

export default function App() {
  const [selected, setSelected] = useState(101);
  const { dashboard, setDashboard, entries, error, activityError, updated, refresh } = useDesk(selected);
  const [pending, setPending] = useState('');
  const [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState('');
  const [filter, setFilter] = useState('all');
  const [instructions, setInstructions] = useState('');
  const ticket = dashboard?.tickets.find(t => t.id === selected);
  const jobs = dashboard?.runs || [];
  const running = jobs.find(j => j.status === 'running');
  const job = jobs.filter(j => j.ticket_id === selected).at(-1);
  const recentRunId = job?.run_id || entries.at(-1)?.run_id;
  const runEntries = entries.filter(e => e.run_id === recentRunId);
  const visible = [...runEntries].reverse().filter(e => describe(e) && (filter === 'all' || (filter === 'tools' ? e.event.startsWith('mcp_') : !!e.role))).slice(0,80);
  const payments = (dashboard?.payment_requests || []).filter(p => p.status === 'pending');
  const purchases = (dashboard?.purchase_orders || []).filter(p => p.status === 'draft');
  const receipts = (dashboard?.purchase_orders || []).filter(p => p.status === 'paid' && (p.received_qty || 0) < p.qty);
  const approvals = payments.length + purchases.length + receipts.length;
  const cash = dashboard?.cash_accounts.find(a => a.name === 'checking');
  const blocked = !!pending || !!running || !!error || !dashboard;
  const toolNames = [...new Set(runEntries.filter(e => e.event === 'mcp_call').map(e => text(e.data.tool_name)))];

  async function run(reviewOnly = false) {
    setPending('run'); setActionError(''); setNotice('');
    try {
      const result = await post<Job>(`/tickets/${selected}/run`, { ...(instructions.trim() ? { prompt:instructions.trim() } : {}), ...(reviewOnly ? {review_only:true} : {}) });
      setDashboard(previous => previous ? { ...previous, runs: [...previous.runs, result] } : previous);
      setNotice(`Ticket ${selected} is running. Watch the team below.`);
      await refresh();
    } catch (e) { setActionError(e instanceof Error ? e.message : 'Run could not start.'); }
    finally { setPending(''); }
  }
  async function decide(kind: string, id: number, body: unknown) {
    setPending(`${kind}-${id}`); setActionError(''); setNotice('');
    try {
      await post(`/approvals/${kind === 'payment' ? 'payments' : 'purchases'}/${id}${kind === 'receipt' ? '/receive' : ''}`, body);
      setNotice(kind === 'payment' ? 'Decision recorded. The balance and approval queue have refreshed.' : kind === 'receipt' ? 'Actual receipt recorded. Run its ticket again to continue fulfillment.' : 'Purchase confirmed. Run its ticket again to prepare payment or continue.');
      await refresh();
    } catch (e) { setActionError(e instanceof Error ? e.message : 'Decision could not be recorded.'); }
    finally { setPending(''); }
  }
  const resolved = dashboard?.tickets.filter(t => t.status === 'resolved').length || 0;
  return <div className="app-shell">
    <aside className="rail"><a href="#top" className="brand-mark" aria-label="Campus Customs home">cc<span>·</span></a><nav aria-label="Dashboard sections"><a href="#tickets" className="rail-link active" aria-label="Tickets"><LayoutDashboard size={20}/></a><a href="#team" className="rail-link" aria-label="Agent team"><Users size={20}/></a><a href="#activity" className="rail-link" aria-label="Activity"><Activity size={20}/></a><a href="#approvals" className="rail-link" aria-label="Approvals"><ShieldCheck size={20}/></a></nav><div className="rail-bottom"><span className="vertical-label">CAMPUS CUSTOMS</span><div className="human-avatar" title="Human oversight">H</div></div></aside>
    <main id="top">
      <header className="page-header"><div><div className="eyebrow"><span className="mint-dot"/> CAMPUS CUSTOMS / MULTI-AGENT OPERATIONS</div><h1>The operations desk<span>.</span></h1><p>Five specialists. One shared shop. You make the final call.</p></div><div className="header-right"><span className={`connection ${error ? 'offline' : dashboard ? '' : 'loading'}`}><span/>{error ? 'Connection lost' : dashboard ? 'Backend connected' : 'Connecting'}</span><div className="date-label">SHOP DATE <strong>{dashboard?.desk[0]?.date_today || '—'}</strong></div></div></header>
      {(error || actionError || activityError) && <div className="alert" role="alert"><div><strong>{error ? 'Backend unavailable' : 'Action needs attention'}</strong><p>{error || actionError || activityError}</p>{error && <small>Start the FastAPI backend at {API}. Last confirmed values remain visible.</small>}</div><button className="button secondary" onClick={() => { setActionError(''); void refresh(); }}><RefreshCw size={15}/>Retry</button></div>}
      {notice && <div className="notice" role="status"><CheckCircle2 size={16}/>{notice}<button className="icon-button" aria-label="Dismiss notification" onClick={() => setNotice('')}><X size={14}/></button></div>}
      <section className="overview" aria-label="Shop overview"><div><span className="overview-icon"><LayoutDashboard size={19}/></span><p>Ticket board<strong>{dashboard ? `${dashboard.tickets.length - resolved} open` : '—'}<small>{dashboard ? `${resolved} resolved` : "Waiting for data"}</small></strong></p></div><div><span className="overview-icon"><Users size={19}/></span><p>Agent team<strong>{dashboard ? (running ? 'Working' : 'Ready') : '—'}<small>5 connected roles</small></strong></p></div><div><span className="overview-icon amber"><FileCheck2 size={19}/></span><p>Human review<strong>{dashboard ? approvals : '—'}<small>pending decisions</small></strong></p></div><div className="cash-overview"><span className="overview-icon mint"><CircleDollarSign size={19}/></span><p>Checking balance<strong>{cash ? money(cash.balance) : '—'}<small>{error ? 'Last confirmed' : 'Database balance'}</small></strong></p></div></section>
      <div className="desk-layout"><section className="ticket-column" id="tickets"><div className="section-title"><h2>Ticket queue</h2><span className="count">{dashboard?.tickets.length ?? '—'}</span></div><p className="muted small queue-intro">Select a ticket to open its workspace.</p><div className="ticket-list">{dashboard ? dashboard.tickets.map(t => <button key={t.id} className={`ticket-card ${selected === t.id ? 'selected' : ''} ${t.status === 'resolved' ? 'resolved' : ''}`} onClick={() => { setSelected(t.id); setInstructions(''); setNotice(''); setActionError(''); }} aria-pressed={selected === t.id}><div className="ticket-top"><span>#{t.id}</span><span className={`badge ${t.status === 'resolved' ? 'mint' : ''}`}>{t.status === 'resolved' ? <Check size={11}/> : <span className="status-dot"/>}{t.status}</span></div><span className="ticket-category">{ticketLabel(t.type)}</span><h3>{t.subject}</h3><p>{t.requester}</p><div className="ticket-bottom"><span>{t.sku ? `${t.qty} unit${t.qty === 1 ? '' : 's'} · ${t.size}` : 'Lease obligation'}</span><ChevronRight size={16}/></div></button>) : <div className="empty"><Loader2 className="spin" size={22}/><p>Loading the ticket board…</p></div>}</div><div className="source-note"><ShieldCheck size={16}/><p>Working copy only.<br/><span>The original shop data stays preserved.</span></p></div></section>
      <section className="workspace"><div className="ticket-detail panel"><div className="detail-heading"><div><span className="eyebrow">TICKET {selected} / {ticket ? ticketLabel(ticket.type).toUpperCase() : 'WORKSPACE'}</span><h2>{ticket?.subject || 'Your next decision starts here'}</h2></div><span className={`badge ${ticket?.status === 'resolved' ? 'mint' : ''}`}>{ticket?.status === 'resolved' ? <CheckCircle2 size={13}/> : <Clock3 size={13}/>} {ticket?.status || 'Loading'}</span></div><p className="detail-requester">Requested by <strong>{ticket?.requester || '—'}</strong></p>{ticket?.notes && <p className="ticket-notes">{ticket.notes}</p>}<div className="detail-facts">{ticket?.sku ? <><span><Shirt size={14}/>{ticket.sku}</span><span>Size {ticket.size}</span><span>{ticket.qty} units requested</span></> : <span><Landmark size={14}/>Facilities & rent</span>}</div><div className="run-controls"><details><summary>Optional instructions</summary><textarea aria-label="Optional instructions for the team" placeholder="Add context for this run…" maxLength={8000} value={instructions} onChange={e => setInstructions(e.target.value)} disabled={blocked}/></details><button className="button primary run-button" onClick={() => void run()} disabled={blocked || ticket?.status !== 'open'}>{running?.ticket_id === selected ? <Loader2 className="spin" size={16}/> : ticket?.status === 'resolved' ? <CheckCircle2 size={16}/> : <Play size={16}/>} {ticket?.status === 'resolved' ? 'Ticket resolved' : pending === 'run' ? 'Starting…' : running?.ticket_id === selected ? 'Team is working' : 'Run ticket'}</button>{ticket?.status === 'resolved' && <button className="button secondary" disabled={blocked} onClick={() => void run(true)}>Review resolved outcome</button>}</div>{running && running.ticket_id !== selected && <p className="muted small">Ticket {running.ticket_id} is running. The shop handles one run at a time.</p>}{job && job.status !== 'running' && <div className={`run-outcome ${job.status === 'failed' ? 'failure' : ''}`}><strong>{job.status === 'failed' ? 'Run stopped' : job.result?.report.outcome.replaceAll('_',' ') || job.status}</strong><p>{job.error || job.result?.report.summary || 'The run has finished.'}</p>{job.result?.usage && <small>{job.result.usage.total_tokens.toLocaleString()} tokens{job.result.usage.estimated_cost_usd !== null && ` · estimated ${money(Number(job.result.usage.estimated_cost_usd))}`}</small>}</div>}</div>
      <section className="team-section" id="team"><div className="section-title"><h2>The agent team</h2><span className="muted small"><span className="mint-dot"/> Fully connected</span></div><div className="agent-grid">{ROLES.map(({ role, initials, purpose, icon: Icon, color }) => {
        const events = runEntries.filter(e => e.role === role);
        const latest = events.at(-1);
        const report = [...events].reverse().find(e => e.event === 'agent_finished')?.data.report as Report | undefined;
        const active = running?.ticket_id === selected && latest && !['agent_finished','agent_failed'].includes(latest.event);
        const state = active ? 'Working' : latest?.event === 'agent_failed' ? 'Stopped' : report ? 'Contributed' : 'Standing by';
        return <article className={`agent-card ${color} ${active ? 'working' : ''}`} key={role}><div className="agent-avatar"><Icon size={20}/><span>{initials}</span></div><h3>{role}</h3><p>{purpose}</p><span className={`agent-state ${active ? 'mint' : ''}`}><span className={active ? 'pulse-dot' : 'status-dot'}/>{state}</span>{report ? <details className="contribution"><summary>View contribution</summary><p>{report.summary}</p><small>{report.outcome.replaceAll('_',' ')}</small></details> : <span className="no-contribution">{active ? 'Following live evidence…' : 'No contribution this run'}</span>}</article>;
      })}</div></section>
      <div className="lower-grid"><section className="activity-panel panel" id="activity"><div className="section-title"><h2><Radio size={17}/> Activity stream</h2><span className={`badge ${running?.ticket_id === selected ? 'mint' : ''}`}>{running?.ticket_id === selected ? 'Live' : 'Recent'}</span></div><div className="stream-tabs" role="group" aria-label="Filter activity">{['all','agents','tools'].map(f => <button key={f} className={filter === f ? 'active' : ''} onClick={() => setFilter(f)} aria-pressed={filter === f}>{f === 'all' ? 'All actions' : f === 'agents' ? 'Agent actions' : 'Tool usage'}</button>)}</div>{toolNames.length > 0 && <div className="tool-summary"><Code2 size={14}/><span>{toolNames.length} distinct MCP tools used</span></div>}<div className="activity-feed" aria-live="polite" aria-relevant="additions">{visible.length ? visible.map(e => <article className={`event ${e.event.startsWith('mcp_') ? 'tool-event' : ''}`} key={e.sequence}><div className="event-icon">{e.event.startsWith('mcp_') ? <Wrench size={14}/> : e.event === 'delegation' ? <ArrowDownRight size={14}/> : <MessageSquare size={14}/>}</div><div className="event-content"><div className="event-meta"><strong>{e.role || 'Team'}</strong><span>{e.event === 'mcp_call' ? 'TOOL CALL' : e.event.replaceAll('_',' ').toUpperCase()}</span><time>{new Date(e.recorded_at_utc).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit', second:'2-digit' })}</time></div><p>{describe(e)}</p>{e.event.startsWith('mcp_') && <details><summary>{e.event === 'mcp_call' ? 'Arguments' : 'Returned evidence'}</summary><pre>{JSON.stringify(e.event === 'mcp_call' ? e.data.arguments : e.data.result || e.data, null, 2)}</pre></details>}</div></article>) : <div className="empty stream-empty"><Activity size={27}/><h3>The next move starts with you.</h3><p>Run this ticket to see agent messages,<br/>delegations, and real tool evidence here.</p></div>}</div></section>
      <section className="approval-panel panel" id="approvals"><div className="section-title"><h2><ShieldCheck size={17}/> Human review</h2><span className="count amber">{approvals}</span></div><p className="muted small">Across the shop. Agents prepare; you approve.</p>{approvals ? <div className="approval-list">{payments.map(p => <Approval key={`pay-${p.id}`} item={p} kind="payment" busy={blocked} onDecide={decide}/>)}{purchases.map(p => <Approval key={`purchase-${p.id}`} item={p} kind="purchase" busy={blocked} onDecide={decide}/>)}{receipts.map(p => <Receipt key={`receipt-${p.id}`} item={p} busy={blocked} onReceive={decide}/>)}</div> : <div className="empty approval-empty"><PackageCheck size={30}/><h3>Nothing waiting on you.</h3><p>Payment requests and purchase drafts<br/>appear here when the team prepares them.</p></div>}<div className="safety-note"><ShieldCheck size={15}/><p>Cash moves only after your payment approval. Purchase confirmation does not spend money.</p></div></section></div>
      </section></div><footer><span><span className="mint-dot"/> Data from the Campus Customs working database</span><span>{updated ? `Last synced ${updated.toLocaleTimeString([], { hour:'2-digit',minute:'2-digit',second:'2-digit' })}` : 'Waiting for first sync'}<button className="icon-button" aria-label="Refresh dashboard" onClick={() => void refresh()}><RefreshCw size={13}/></button></span></footer>
    </main>
  </div>;
}
