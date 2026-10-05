"""HTTP routes against real MCP operations on disposable databases; no paid models."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import httpx
from fastmcp import Client
from backend.main import create_app
from backend.mcp_client import AGENT_TOOLS
from backend.audit import AuditTrail
from mcp_server import database, server


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)
        self.folder = ROOT/'output'/('p7-fixture-'+str(uuid4()))
        self.folder.mkdir()
        self.original = ROOT/'data/campus_customs.db'
        self.hash = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.saved = database.DB_PATH
        database.DB_PATH = self.folder/'working.db'
        shutil.copyfile(self.original,database.DB_PATH)
        self.saved_key = os.environ.get('CAMPUS_HUMAN_APPROVAL_KEY')
        os.environ['CAMPUS_HUMAN_APPROVAL_KEY'] = 'offline-http-human'
        self.mcp = Client(server.mcp)
        await self.mcp.__aenter__()
        client = self.mcp
        class FixtureShop:
            def __init__(self,human=False): self.human=human
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def call(self,name,args):
                if not self.human and name not in AGENT_TOOLS:
                    raise PermissionError('Human tool denied to agent.')
                return (await client.call_tool(name,args)).structured_content
        self.event = asyncio.Event()
        event = self.event
        class OfflineTeam:
            async def run(self,prompt,ticket_id,run_id,_audit,review_only=False):
                _audit.append(run_id,'offline_http_run',prompt=prompt,ticket_id=ticket_id)
                await event.wait()
                return {'run_id':run_id,'report':{'outcome':'awaiting_human'}}
        self.audit = self.folder/'audit.json'
        AuditTrail(self.audit).append('earlier','preserved_entry')
        self.app=create_app(shop_factory=FixtureShop,team_factory=OfflineTeam,audit_path=self.audit)
        self.life=self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.http=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://test')

    async def asyncTearDown(self):
        await self.http.aclose()
        await self.life.__aexit__(None,None,None)
        await self.mcp.__aexit__(None,None,None)
        database.DB_PATH=self.saved
        if self.saved_key is None: os.environ.pop('CAMPUS_HUMAN_APPROVAL_KEY',None)
        else: os.environ['CAMPUS_HUMAN_APPROVAL_KEY']=self.saved_key
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(),self.hash)
        shutil.rmtree(self.folder)

    async def tool(self,name,**args):
        return (await self.mcp.call_tool(name,args)).structured_content

    async def test_read_run_poll_activity_and_busy_reset(self):
        self.assertEqual(len((await self.http.get('/tickets')).json()['tickets']),3)
        self.assertEqual((await self.http.get('/cash')).json()['balance'],3400)
        self.assertEqual((await self.http.post('/tickets/999/run',json={})).status_code,404)
        response=await self.http.post('/tickets/101/run',json={'prompt':'Offline HTTP test prompt'})
        self.assertEqual(response.status_code,202)
        run_id=response.json()['run_id']
        self.assertEqual((await self.http.post('/reset',json={'approved_by':'Human','confirm':True})).status_code,409)
        self.event.set()
        for _ in range(20):
            await asyncio.sleep(.01)
            status=(await self.http.get('/runs/'+run_id)).json()
            if status['status']=='completed': break
        self.assertEqual(status['status'],'completed')
        history=(await self.http.get('/activity',params={'run_id':run_id})).json()['entries']
        self.assertEqual(history[0]['data']['prompt'],'Offline HTTP test prompt')
        self.assertEqual((await self.http.get('/approvals')).json()['payment_requests'],[])
        self.assertEqual((await self.http.get('/runs/missing')).status_code,404)

    async def test_payment_replay_rejection_cash_and_reset(self):
        request=await self.tool('request_payment',ticket_id=101,kind='invoice')
        self.assertEqual((await self.http.get('/cash')).json()['balance'],3400)
        self.assertNotIn('execute_approved_payment',AGENT_TOOLS)
        with self.assertRaises(Exception):
            await self.tool('execute_approved_payment',request_id=request['id'],approved_by='Agent',approval_secret='wrong')
        body={'approved':True,'approved_by':'Test Human'}
        path='/approvals/payments/'+str(request['id'])
        first=await self.http.post(path,json=body)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual((await self.http.post(path,json=body)).json(),first.json())
        self.assertEqual((await self.http.get('/cash')).json()['balance'],2560)
        rent=await self.tool('request_payment',ticket_id=102,kind='rent')
        reject=await self.http.post('/approvals/payments/'+str(rent['id']),json={'approved':False,'approved_by':'Test Human'})
        self.assertEqual(reject.json()['status'],'rejected')
        self.assertEqual((await self.http.get('/cash')).json()['balance'],2560)
        self.assertEqual((await self.http.post('/reset',json={'approved_by':'Human','confirm':False})).status_code,422)
        reset=await self.http.post('/reset',json={'approved_by':'Human','confirm':True})
        self.assertEqual(reset.status_code,200,reset.text)
        self.assertEqual((await self.http.get('/cash')).json()['balance'],3400)
        self.assertEqual((await self.http.get('/approvals')).json()['payment_requests'],[])
        self.assertEqual(json.loads(self.audit.read_text())[0]['event'],'preserved_entry')

    async def test_purchase_and_failed_payment_transaction(self):
        draft=await self.tool('draft_purchase_order',ticket_id=103,vendor_id=2,qty=12)
        order=draft['draft']['id']
        confirmed=await self.http.post('/approvals/purchases/'+str(order),json={'approved':True,'approved_by':'Human','confirmed_unit_cost':100})
        self.assertEqual(confirmed.status_code,200,confirmed.text)
        self.assertEqual((await self.http.get('/cash')).json()['balance'],3400)
        rent=await self.tool('request_payment',ticket_id=102,kind='rent')
        self.assertEqual((await self.http.post('/approvals/payments/'+str(rent['id']),json={'approved':True,'approved_by':'Human'})).status_code,200)
        purchase=await self.tool('request_payment',ticket_id=103,kind='purchase_order',purchase_order_id=order)
        refusal=await self.http.post('/approvals/payments/'+str(purchase['id']),json={'approved':True,'approved_by':'Human'})
        self.assertEqual(refusal.status_code,409)
        board=await self.tool('read_shop_board')
        self.assertEqual(board['cash_accounts'][0]['balance'],1000)
        self.assertEqual(next(r for r in board['approval_requests'] if r['id']==purchase['id'])['status'],'pending')
        self.assertEqual((await self.http.post('/reset',headers={'Origin':'https://untrusted.example'},json={'approved_by':'Human','confirm':True})).status_code,403)
        self.assertEqual((await self.http.post('/approvals/payments/1',json={'approved':'yes','approved_by':'Human'})).status_code,422)

    async def test_dashboard_snapshot_cors_and_test_history_filter(self):
        response=await self.http.get('/dashboard')
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()['tickets']),3)
        self.assertEqual(response.json()['cash_accounts'][0]['balance'],3400)
        trail=AuditTrail(self.audit)
        trail.append('fixture-test','team_started',model='offline-test')
        trail.append('fixture-test','agent_started',ticket_id=101)
        trail.append('fixture-live','agent_started',ticket_id=101)
        response=await self.http.get('/activity',params={'ticket_id':101,'include_test_runs':'false'})
        self.assertEqual({e['run_id'] for e in response.json()['entries']},{'fixture-live'})
        preflight=await self.http.options('/dashboard',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'GET'})
        self.assertEqual(preflight.headers['access-control-allow-origin'],'http://localhost:5173')

    async def test_human_receipt_and_fulfillment_without_second_cash_charge(self):
        draft = await self.tool('draft_purchase_order',ticket_id=101,vendor_id=1,qty=1)
        order = draft['draft']['id']
        path = f'/approvals/purchases/{order}/receive'
        receipt = {'approved_by':'Test Human','received_qty':1,'confirm':True}
        self.assertEqual((await self.http.post(path,json=receipt)).status_code,409)
        req = await self.tool('request_payment',ticket_id=101,kind='invoice')
        self.assertEqual((await self.http.post(f'/approvals/payments/{req["id"]}',json={'approved':True,'approved_by':'Test Human'})).status_code,200)
        confirmation = await self.http.post(f'/approvals/purchases/{order}',json={'approved':True,'approved_by':'Test Human','confirmed_unit_cost':8,'covered_by_paid_invoice':True,'simulation_note':'Explicitly authorized fixture quote and invoice coverage, not fetched facts.'})
        self.assertEqual(confirmation.status_code,200,confirmation.text)
        self.assertEqual((await self.http.post(path,json={**receipt,'confirm':False})).status_code,422)
        self.assertEqual((await self.http.post(path,json={**receipt,'received_qty':2})).status_code,409)
        self.assertEqual((await self.http.post(path,json={**receipt,'simulation_note':'Explicitly authorized fixture receipt, not physical observation.'})).status_code,200)
        self.assertEqual((await self.http.post(path,json=receipt)).status_code,409)
        await self.tool('fulfill_ticket_order',ticket_id=101)
        board = await self.tool('read_shop_board')
        self.assertEqual(board['tickets'][0]['status'],'resolved')
        self.assertEqual(board['cash_accounts'][0]['balance'],2560)
        self.assertEqual(len(board['supply_evidence']),2)
        self.assertTrue(all(e['source']=='user_authorized_simulation' for e in board['supply_evidence']))
        self.assertEqual((await self.http.post('/tickets/101/run',json={})).status_code,409)
        self.event.set()
        self.assertEqual((await self.http.post('/tickets/101/run',json={'review_only':True})).status_code,202)


if __name__=='__main__': unittest.main()
