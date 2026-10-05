import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import type { Dashboard, Entry } from './api';

let snapshot: Dashboard;
let events: Entry[];
let calls: {path: string; body: Record<string, unknown>}[];
let runFailure: boolean;
const base: Dashboard = {
  tickets: [
    {id:101,type:'customer_order',requester:'Tauhid Zaman',subject:'Bulldog tee',status:'open',notes:'Needs a tee in size S.',sku:'CC-TEE-WHITE',size:'S',qty:1},
    {id:102,type:'rent_notice',requester:'Elm City Properties',subject:'Rent due',status:'open',notes:null,sku:null,size:null,qty:null},
    {id:103,type:'price_override',requester:'Yale AI Club',subject:'Bulk hoodie discount',status:'open',notes:'Bulk discount request',sku:'CC-HOOD-NAVY',size:'M',qty:20},
  ],cash_accounts:[{name:'checking',balance:3400,date:'2026-08-31'}],desk:[{date_today:'2026-08-31'}],payment_requests:[],purchase_orders:[],runs:[],
};
beforeEach(() => {
  snapshot=structuredClone(base); events=[]; calls=[]; runFailure=false;
  vi.stubGlobal('fetch',vi.fn(async (url: string, options?: RequestInit) => {
    const path = new URL(url).pathname;
    const body=JSON.parse(String(options?.body || '{}')) as Record<string,unknown>;
    if (options?.method==='POST') calls.push({path,body});
    let data: unknown;
    if (path==='/dashboard') data=structuredClone(snapshot);
    else if (path==='/activity') data={entries:events,next_sequence:events.at(-1)?.sequence || 0};
    else if (path==='/tickets/101/run') {
      if (runFailure) return new Response(JSON.stringify({detail:'Price ceilings are not configured.'}),{status:503});
      const job={run_id:'fixture-run',ticket_id:101,status:'running'};
      snapshot.runs=[job];data=job;
      events=[{sequence:1,recorded_at_utc:'2026-08-31T12:00:00Z',run_id:'fixture-run',event:'agent_started',role:'Boss',data:{ticket_id:101}},
        {sequence:2,recorded_at_utc:'2026-08-31T12:00:01Z',run_id:'fixture-run',event:'mcp_call',role:'Boss',data:{tool_name:'read_shop_board',arguments:{}}},
        {sequence:3,recorded_at_utc:'2026-08-31T12:00:02Z',run_id:'fixture-run',event:'agent_finished',role:'Inventory',data:{report:{summary:'Confirmed exact-size stock shortfall.',outcome:'awaiting_human'}}}];
    } else if (path==='/approvals/payments/1') {
      if (body.approved) snapshot.cash_accounts[0].balance=2560;
      snapshot.payment_requests=[];data={id:1,amount:840};
    } else if (path==='/approvals/purchases/2') {snapshot.purchase_orders=[];data={id:2,status:'confirmed'};}
    else if (path==='/approvals/purchases/2/receive') {snapshot.purchase_orders=[];data={id:2,status:'received'};}
    else return new Response('{}',{status:404});
    return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});
  }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

describe('Dashboard behavior (test-only API fixtures)',()=>{
  it('renders real-shaped shop data and changes the selected ticket',async()=>{
    render(<App/>);const user=userEvent.setup();
    await screen.findByText('$3,400.00');
    expect(screen.getAllByRole('button',{name:/#10[123]/}).length).toBe(3);
    await user.click(screen.getByRole('button',{name:/#103/}));
    expect(screen.getByRole('heading',{name:'Bulk hoodie discount',level:2})).toBeTruthy();
    expect(screen.getByText('CC-HOOD-NAVY')).toBeTruthy();
    expect(screen.getAllByText('No contribution this run').length).toBe(5);
  });
  it('keeps a ticket open and shows a refused-run error',async()=>{
    runFailure=true;render(<App/>);const user=userEvent.setup();await screen.findByText('$3,400.00');
    await user.click(screen.getByRole('button',{name:'Run ticket'}));
    await screen.findByText('Price ceilings are not configured.');
    expect(screen.queryByRole('button',{name:'Ticket resolved'})).toBeNull();
    expect(calls[0].path).toBe('/tickets/101/run');
  });
  it('requires human review and updates cash after a payment decision',async()=>{
    snapshot.payment_requests=[{id:1,ticket_id:101,kind:'invoice',ref_id:501,obligation_date:'2026-08-28',amount:840,account:'checking',status:'pending',approved_by:null}];
    render(<App/>);const user=userEvent.setup();await screen.findByText('$3,400.00');
    await user.click(screen.getByRole('button',{name:'Review payment'}));
    expect((screen.getByRole('button',{name:'Approve & pay'}) as HTMLButtonElement).disabled).toBe(true);
    await user.type(screen.getByLabelText('Your name'),'Fixture Human');
    await user.click(screen.getByLabelText('I approve this $840.00 payment.'));
    await user.click(screen.getByRole('button',{name:'Approve & pay'}));
    await screen.findByText('$2,560.00');
    expect(calls[0]).toEqual({path:'/approvals/payments/1',body:{approved:true,approved_by:'Fixture Human'}});
    expect(screen.queryByRole('button',{name:'Review payment'})).toBeNull();
  });
  it('requires a real quote for purchase confirmation and does not change cash',async()=>{
    snapshot.purchase_orders=[{id:2,ticket_id:103,vendor_id:2,sku:'CC-HOOD-NAVY',size:'M',qty:12,unit_cost:22,status:'draft'}];
    render(<App/>);const user=userEvent.setup();await screen.findByText('$3,400.00');
    await user.click(screen.getByRole('button',{name:'Review purchase'}));
    await user.type(screen.getByLabelText('Your name'),'Fixture Human');
    await user.click(screen.getByLabelText('I verified this supplier and actual quote.'));
    expect((screen.getByRole('button',{name:'Confirm purchase'}) as HTMLButtonElement).disabled).toBe(true);
    await user.type(screen.getByLabelText('Actual quoted unit cost ($)'),'22');
    await user.click(screen.getByRole('button',{name:'Confirm purchase'}));
    await waitFor(()=>expect(calls.length).toBe(1));
    expect(calls[0].body.confirmed_unit_cost).toBe(22);
    expect(screen.getByText('$3,400.00')).toBeTruthy();
  });
  it('polls tool evidence and contributions, then marks resolution from stored status',async()=>{
    render(<App/>);const user=userEvent.setup();await screen.findByText('$3,400.00');
    await user.click(screen.getByRole('button',{name:'Run ticket'}));
    await screen.findByRole('button',{name:'Team is working'});
    await screen.findByText('read_shop_board',{}, {timeout:4000});
    await user.click(screen.getByText('View contribution'));
    const team=screen.getByRole('heading',{name:'The agent team'}).parentElement!.parentElement!;
    expect(within(team).getByText('Confirmed exact-size stock shortfall.')).toBeTruthy();
    snapshot.tickets[0].status='resolved';snapshot.runs[0].status='completed';
    await user.click(screen.getByRole('button',{name:'Refresh dashboard'}));
    await screen.findByRole('button',{name:'Ticket resolved'});
    expect((screen.getByRole('button',{name:'Ticket resolved'}) as HTMLButtonElement).disabled).toBe(true);
  });
  it('requires actual receipt attestation and a quantity within the paid order',async()=>{
    snapshot.purchase_orders=[{id:2,ticket_id:101,vendor_id:1,sku:'CC-TEE-WHITE',size:'S',qty:1,unit_cost:8,status:'paid',received_qty:0}];
    render(<App/>);const user=userEvent.setup();await screen.findByText('$3,400.00');
    const button=screen.getByRole('button',{name:'Record actual receipt'}) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    await user.type(screen.getByLabelText('Your name'),'Fixture Human');
    await user.type(screen.getByLabelText('Quantity actually received'),'2');
    await user.click(screen.getByLabelText('I physically verified these exact SKU/size units.'));
    expect(button.disabled).toBe(true);
    await user.clear(screen.getByLabelText('Quantity actually received'));
    await user.type(screen.getByLabelText('Quantity actually received'),'1');
    await user.click(button);
    await waitFor(()=>expect(calls.length).toBe(1));
    expect(calls[0]).toEqual({path:'/approvals/purchases/2/receive',body:{approved_by:'Fixture Human',received_qty:1,confirm:true}});
    expect(screen.getByText('$3,400.00')).toBeTruthy();
  });
});
