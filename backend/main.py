"""Dashboard API. Shop records and mutations are exclusively MCP operations."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import secrets
import sys
from uuid import uuid4

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.audit import AuditTrail, file_lock
from backend.config import ROOT, load_environment
from backend.mcp_client import ShopMCP
from backend.team import CampusTeam
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.models import RunRequest, HumanDecision, PurchaseDecision, ResetRequest, ReceiptDecision


def create_app(*, shop_factory=ShopMCP, team_factory=CampusTeam, audit_path=None):
    audit_path = audit_path or ROOT / 'output/audit_trail.json'
    jobs = {}
    tasks = set()
    gate = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        load_environment()
        # Credential stays in server memory/environment, never in HTTP responses or agent tools.
        if not os.getenv('CAMPUS_HUMAN_APPROVAL_KEY'):
            os.environ['CAMPUS_HUMAN_APPROVAL_KEY'] = secrets.token_urlsafe(32)
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title='Campus Customs dashboard API', lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[f'http://{host}:{port}' for host in ('localhost','127.0.0.1') for port in (5173,3000,8916)], allow_methods=['GET','POST'], allow_headers=['Content-Type'])

    @app.middleware('http')
    async def local_mutations(request: Request, call_next):
        origin = request.headers.get('origin')
        allowed = {f'http://{host}:{port}' for host in ('localhost','127.0.0.1') for port in (5173,3000,8916,8000)}
        if request.method == 'POST' and origin and origin not in allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Untrusted browser origin.'}, status_code=403)
        return await call_next(request)

    async def call(name, args=None, human=False):
        try:
            async with shop_factory(human=human) as shop:
                return await shop.call(name, args or {})
        except Exception as exc:
            # MCP business failures are visible; never include secret-bearing request arguments.
            raise HTTPException(409, f'MCP operation refused: {exc}') from exc

    async def board():
        return await call('read_shop_board')

    def credential(name):
        return {'approved_by':name, 'approval_secret':os.environ['CAMPUS_HUMAN_APPROVAL_KEY']}

    async def mutation(tool, args, actor):
        if gate.locked():
            raise HTTPException(409, 'An agent run or human operation is active; retry after it finishes.')
        async with gate:
            result = await call(tool, args, human=True)
            AuditTrail(audit_path).append(str(uuid4()), 'human_api_action', tool=tool, approved_by=actor, result=result)
            return result

    @app.get('/dashboard')
    async def dashboard():
        b = await board()
        return {'tickets':b['tickets'], 'cash_accounts':b['cash_accounts'],
                'desk':b['desk'], 'payment_requests':b['approval_requests'],
                'purchase_orders':b['purchase_order_drafts'], 'runs':list(jobs.values())}

    @app.get('/tickets')
    async def tickets():
        return {'tickets':(await board())['tickets']}

    @app.post('/tickets/{ticket_id}/run', status_code=202)
    async def run_ticket(ticket_id: int, body: RunRequest):
        record = next((t for t in (await board())['tickets'] if t['id']==ticket_id),None)
        if record is None:
            raise HTTPException(404, 'Ticket not found.')
        if record['status']!='open' and not body.review_only:
            raise HTTPException(409, 'Ticket is already resolved.')
        if gate.locked():
            raise HTTPException(409, 'Another run or human operation is active.')
        try:
            team = team_factory()
        except Exception as exc:
            raise HTTPException(503, str(exc)) from exc
        await gate.acquire()
        run_id = str(uuid4())
        job = {'run_id':run_id, 'ticket_id':ticket_id, 'status':'running'}
        jobs[run_id] = job

        async def execute():
            try:
                job['result'] = await team.run(body.prompt,ticket_id=ticket_id,run_id=run_id,_audit=AuditTrail(audit_path),review_only=body.review_only)
                job['status'] = 'completed'
            except asyncio.CancelledError:
                job.update(status='cancelled',error='Backend stopped during run.')
                raise
            except Exception as exc:
                job.update(status='failed',error=str(exc))
                AuditTrail(audit_path).append(run_id,'api_run_failed',error_type=type(exc).__name__)
            finally:
                gate.release()
        task = asyncio.create_task(execute())
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return dict(job)

    @app.get('/runs/{run_id}')
    async def run_status(run_id: str):
        if run_id not in jobs:
            raise HTTPException(404, 'Run not found in this backend session; history remains in /activity.')
        return jobs[run_id]

    @app.get('/activity')
    async def activity(after: int = Query(0,ge=0), limit: int = Query(100,ge=1,le=500), run_id: str | None = None, ticket_id: int | None = None, include_test_runs: bool = True):
        try:
            with file_lock(audit_path.with_suffix('.lock')):
                entries = json.loads(audit_path.read_text(encoding='utf-8')) if audit_path.exists() else []
            if not isinstance(entries,list):
                raise ValueError('Audit trail must be an array.')
        except (ValueError,OSError) as exc:
            raise HTTPException(503,'Audit trail is unavailable or invalid.') from exc
        excluded = {e['run_id'] for e in entries if e['event']=='team_started' and e['data'].get('model')=='offline-test'} if not include_test_runs else set()
        ticket_runs = {e['run_id'] for e in entries if e['data'].get('ticket_id')==ticket_id} if ticket_id is not None else None
        entries = [e for e in entries if e['run_id'] not in excluded and (ticket_runs is None or e['run_id'] in ticket_runs)]
        selected = [e for e in entries if e['sequence']>after and (run_id is None or e['run_id']==run_id)]
        # Cursor reads the next batch, initial no-cursor view shows the most recent batch.
        batch = selected[:limit] if after else selected[-limit:]
        return {'entries':batch,'next_sequence':batch[-1]['sequence'] if batch else after}

    @app.get('/approvals')
    async def approvals():
        b = await board()
        return {'payment_requests':b['approval_requests'],'purchase_orders':b['purchase_order_drafts']}

    @app.post('/approvals/payments/{request_id}')
    async def payment(request_id: int, body: HumanDecision):
        return await mutation('approve_and_pay',{'request_id':request_id,'approved':body.approved,**credential(body.approved_by)},body.approved_by)

    @app.post('/approvals/purchases/{purchase_order_id}')
    async def purchase(purchase_order_id: int, body: PurchaseDecision):
        if not body.approved:
            raise HTTPException(422,'Purchase confirmation requires approved=true; unapproved drafts remain proposals.')
        return await mutation('confirm_purchase_order',{'purchase_order_id':purchase_order_id,'confirmed_unit_cost':body.confirmed_unit_cost,'covered_by_paid_invoice':body.covered_by_paid_invoice,'simulation_note':body.simulation_note,**credential(body.approved_by)},body.approved_by)

    @app.get('/cash')
    async def cash():
        account = next((a for a in (await board())['cash_accounts'] if a['name']=='checking'),None)
        if account is None:
            raise HTTPException(404,'Checking account is missing.')
        return account

    @app.post('/approvals/purchases/{purchase_order_id}/receive')
    async def receive(purchase_order_id: int, body: ReceiptDecision):
        if not body.confirm:
            raise HTTPException(422, 'Explicit actual-receipt confirmation is required.')
        return await mutation('receive_purchase_order', {'purchase_order_id':purchase_order_id,
                              'received_qty':body.received_qty,'simulation_note':body.simulation_note, **credential(body.approved_by)}, body.approved_by)

    @app.post('/reset')
    async def reset(body: ResetRequest):
        if not body.confirm:
            raise HTTPException(422,'Explicit confirm=true is required to reset the working database.')
        return await mutation('reset_working_database',credential(body.approved_by),body.approved_by)

    return app


app = create_app()
