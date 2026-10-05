"""Offline checks: real MCP tools on a disposable SQLite copy; no paid AI calls."""

import asyncio
from contextlib import closing
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from fastmcp import Client
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage

from backend.audit import AuditTrail
from backend.config import MODEL_NAME, PORTKEY_BASE_URL
from backend.mcp_client import AGENT_TOOLS
from backend.models import Role, RunBudget
from backend.team import CampusTeam, SharedRun, AgentDeps
from mcp_server import database, operations, server


def scripted_model(role):
    """Deterministic protocol responder, not an AI/provider model."""
    async def respond(messages, info):
        prompts=[p.content for m in messages if isinstance(m,ModelRequest) for p in m.parts if isinstance(p,UserPromptPart)]
        exercise=any("EXERCISE_ALL_PEERS" in str(p) for p in prompts)
        calls=[p for m in messages if isinstance(m,ModelResponse) for p in m.parts if isinstance(p,ToolCallPart)]
        if not any(c.tool_name=="shop_tool" for c in calls):
            part=ToolCallPart("shop_tool",{"tool_name":"read_shop_board","arguments":{}})
        else:
            delegated=[c.args_as_dict()["target"] for c in calls if c.tool_name=="delegate"]
            peers=[r for r in Role if r!=role and r.value not in delegated]
            if exercise and peers:
                part=ToolCallPart("delegate",{"target":peers[0].value,"task":"Read live MCP evidence and return an investigated report without further delegation."})
            else:
                part=ToolCallPart(info.output_tools[0].name,{"role":role.value,"ticket_id":None,"outcome":"investigated","summary":"Offline protocol test completed using MCP evidence.","evidence":["read_shop_board"],"next_actions":[]})
        return ModelResponse(parts=[part],usage=RequestUsage(input_tokens=20,output_tokens=10))
    return FunctionModel(respond)


class MCPAdapter:
    def __init__(self,client):
        self.client=client

    async def call(self,name,arguments):
        if name not in AGENT_TOOLS:
            raise PermissionError("Human-only tool blocked from agents.")
        return (await self.client.call_tool(name,arguments)).structured_content


class BusinessSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)
        self.folder=ROOT / "output" / ("test-fixture-"+str(uuid4()))
        self.folder.mkdir()
        self.fixture=self.folder / "shop.db"
        shutil.copyfile(ROOT / "data/campus_customs.db",self.fixture)
        self.saved_path=database.DB_PATH
        database.DB_PATH=self.fixture
        self.saved_key=os.environ.get("CAMPUS_HUMAN_APPROVAL_KEY")
        os.environ["CAMPUS_HUMAN_APPROVAL_KEY"]="offline-fixture-human-credential"
        self.client=Client(server.mcp)
        await self.client.__aenter__()

    async def asyncTearDown(self):
        await self.client.__aexit__(None,None,None)
        database.DB_PATH=self.saved_path
        if self.saved_key is None:
            os.environ.pop("CAMPUS_HUMAN_APPROVAL_KEY",None)
        else:
            os.environ["CAMPUS_HUMAN_APPROVAL_KEY"]=self.saved_key
        shutil.rmtree(self.folder)

    async def call(self,name,**kwargs):
        if name == "execute_approved_payment":
            kwargs.update(approved_by="Offline Human", approval_secret="offline-fixture-human-credential")
        return (await self.client.call_tool(name,kwargs)).structured_content

    async def approve(self,request):
        return await self.call("authorize_payment",request_id=request["id"],approved=True,approved_by="Offline Human",approval_secret="offline-fixture-human-credential")

    async def test_approval_cash_rent_replay_and_dates(self):
        invoice=await self.call("request_payment",ticket_id=101,kind="invoice")
        replay=await self.call("request_payment",ticket_id=101,kind="invoice")
        self.assertEqual(invoice["id"],replay["id"])
        with self.assertRaises(Exception):
            await self.call("execute_approved_payment",request_id=invoice["id"])
        with self.assertRaises(Exception):
            await self.call("authorize_payment",request_id=invoice["id"],approved=True,approved_by="Agent",approval_secret="wrong")
        await self.approve(invoice)
        paid=await self.call("execute_approved_payment",request_id=invoice["id"])
        self.assertEqual(paid["amount"],840)
        self.assertEqual(paid["paid_at"],"2026-08-31")
        self.assertEqual(await self.call("execute_approved_payment",request_id=invoice["id"]),paid)
        rent=await self.call("request_payment",ticket_id=102,kind="rent")
        await self.approve(rent)
        await self.call("execute_approved_payment",request_id=rent["id"])
        closed=await self.call("close_paid_rent_ticket",ticket_id=102)
        self.assertEqual(closed["status"],"resolved")
        board=await self.call("read_shop_board")
        self.assertEqual(board["cash_accounts"][0]["balance"],160)
        self.assertEqual(board["leases"][0]["next_due"],"2026-10-02")
        self.assertEqual(len(board["payments"]),2)

    async def test_insufficient_cash_rolls_back_everything(self):
        request=await self.call("request_payment",ticket_id=102,kind="rent")
        await self.approve(request)
        with closing(__import__('sqlite3').connect(self.fixture)) as conn:
            conn.execute("UPDATE cash_accounts SET balance=100")
            conn.commit()
        before=await self.call("read_shop_board")
        with self.assertRaises(Exception):
            await self.call("execute_approved_payment",request_id=request["id"])
        self.assertEqual(before,await self.call("read_shop_board"))

    async def test_stale_approval_and_rejection(self):
        request=await self.call("request_payment",ticket_id=101,kind="invoice")
        await self.approve(request)
        with closing(__import__('sqlite3').connect(self.fixture)) as conn:
            conn.execute("UPDATE invoices SET amount=900")
            conn.commit()
        before=await self.call("read_shop_board")
        with self.assertRaises(Exception):
            await self.call("execute_approved_payment",request_id=request["id"])
        self.assertEqual(before,await self.call("read_shop_board"))
        rent=await self.call("request_payment",ticket_id=102,kind="rent")
        await self.call("authorize_payment",request_id=rent["id"],approved=False,approved_by="Offline Human",approval_secret="offline-fixture-human-credential")
        with self.assertRaises(Exception):
            await self.call("execute_approved_payment",request_id=rent["id"])

    async def test_drafts_quotes_vendor_block_receipt_and_fulfillment(self):
        draft=await self.call("draft_purchase_order",ticket_id=101,vendor_id=1,qty=1)
        order=draft["draft"]
        self.assertEqual(len(draft["open_invoices"]),1)
        with self.assertRaises(Exception):
            await self.call("request_payment",ticket_id=101,kind="purchase_order",purchase_order_id=order["id"])
        await self.call("confirm_purchase_order",purchase_order_id=order["id"],confirmed_unit_cost=8,approved_by="Offline Human",approval_secret="offline-fixture-human-credential")
        purchase=await self.call("request_payment",ticket_id=101,kind="purchase_order",purchase_order_id=order["id"])
        await self.approve(purchase)
        with self.assertRaises(Exception):
            await self.call("execute_approved_payment",request_id=purchase["id"])
        invoice=await self.call("request_payment",ticket_id=101,kind="invoice")
        await self.approve(invoice)
        await self.call("execute_approved_payment",request_id=invoice["id"])
        await self.call("execute_approved_payment",request_id=purchase["id"])
        with self.assertRaises(Exception):
            await self.call("fulfill_ticket_order",ticket_id=101)
        with self.assertRaises(Exception):
            await self.call("receive_purchase_order",purchase_order_id=order["id"],received_qty=2,approved_by="Offline Human",approval_secret="offline-fixture-human-credential")
        await self.call("receive_purchase_order",purchase_order_id=order["id"],received_qty=1,approved_by="Offline Human",approval_secret="offline-fixture-human-credential")
        with self.assertRaises(Exception):
            await self.call("receive_purchase_order",purchase_order_id=order["id"],received_qty=1,approved_by="Offline Human",approval_secret="offline-fixture-human-credential")
        balance=(await self.call("read_shop_board"))["cash_accounts"][0]["balance"]
        resolved=await self.call("fulfill_ticket_order",ticket_id=101)
        self.assertEqual(resolved["ticket"]["status"],"resolved")
        self.assertEqual(resolved["inventory"]["qty"],0)
        self.assertEqual((await self.call("read_shop_board"))["cash_accounts"][0]["balance"],balance)
        with self.assertRaises(Exception):
            await self.call("fulfill_ticket_order",ticket_id=101)

    async def test_discount_and_exact_size_stock_guard(self):
        with self.assertRaises(Exception):
            await self.call("record_discount_decision",ticket_id=103,unit_price=21,rationale="Below cost")
        await self.call("record_discount_decision",ticket_id=103,unit_price=50,rationale="Offline proposal")
        before=await self.call("read_shop_board")
        with self.assertRaises(Exception):
            await self.call("fulfill_ticket_order",ticket_id=103)
        self.assertEqual(before,await self.call("read_shop_board"))
        row=await self.call("save_board_draft",ticket_id=103,audience="customer",body="This is an unsent proposal.")
        self.assertEqual(row,await self.call("save_board_draft",ticket_id=103,audience="customer",body="This is an unsent proposal."))
        with self.assertRaises(Exception):
            await self.call("close_paid_rent_ticket",ticket_id=102)
        draft=await self.call("draft_purchase_order",ticket_id=103,vendor_id=1,qty=12)
        await self.call("confirm_purchase_order",purchase_order_id=draft["draft"]["id"],confirmed_unit_cost=55,approved_by="Offline Human",approval_secret="offline-fixture-human-credential")
        with self.assertRaises(Exception):
            await self.call("record_discount_decision",ticket_id=103,unit_price=50,rationale="Below confirmed supplier quote")

    async def test_concurrent_payment_execution_only_charges_once(self):
        request=await self.call("request_payment",ticket_id=101,kind="invoice")
        await self.approve(request)
        first,second=await asyncio.gather(
            self.call("execute_approved_payment",request_id=request["id"]),
            self.call("execute_approved_payment",request_id=request["id"]),
        )
        self.assertEqual(first,second)
        board=await self.call("read_shop_board")
        self.assertEqual(len(board["payments"]),1)
        self.assertEqual(board["cash_accounts"][0]["balance"],2560)

    async def test_paid_reprint_invoice_can_fund_confirmed_goods_without_double_charge(self):
        invoice=await self.call("request_payment",ticket_id=101,kind="invoice")
        await self.approve(invoice)
        await self.call("execute_approved_payment",request_id=invoice["id"])
        draft=await self.call("draft_purchase_order",ticket_id=101,vendor_id=1,qty=1)
        order=await self.call("confirm_purchase_order",purchase_order_id=draft["draft"]["id"],confirmed_unit_cost=8,covered_by_paid_invoice=True,approved_by="Offline Human",approval_secret="offline-fixture-human-credential")
        self.assertEqual(order["funding_invoice_id"],501)
        self.assertEqual(order["status"],"paid")
        await self.call("receive_purchase_order",purchase_order_id=order["id"],received_qty=1,approved_by="Offline Human",approval_secret="offline-fixture-human-credential")
        await self.call("fulfill_ticket_order",ticket_id=101)
        board=await self.call("read_shop_board")
        self.assertEqual(len(board["payments"]),1)
        self.assertEqual(board["cash_accounts"][0]["balance"],2560)

    async def test_agent_cycle_role_and_budget_boundaries(self):
        budget=RunBudget(input_usd_per_million="1000000",output_usd_per_million="1000000")
        team=CampusTeam(budget,_test_models={r:scripted_model(r) for r in Role})
        shared=SharedRun(MCPAdapter(self.client),AuditTrail(self.folder / "guards.json"),budget)
        with self.assertRaises(RuntimeError):
            team._before_request(shared)
        shared.budget=RunBudget(max_total_tokens=100000)
        shared.usage.input_tokens=0
        callback_deps=AgentDeps(shared,Role.INVENTORY,(Role.BOSS,Role.INVENTORY))
        callback=team.agents[Role.INVENTORY]._function_toolset.tools["delegate"].function
        report=await callback(SimpleNamespace(deps=callback_deps),Role.BOSS,"Read MCP evidence and answer this focused callback; do not delegate further.")
        self.assertEqual(report["role"],"Boss")
        repeat_deps=AgentDeps(shared,Role.BOSS,(Role.BOSS,Role.INVENTORY,Role.BOSS))
        with self.assertRaises(Exception):
            await team.agents[Role.BOSS]._function_toolset.tools["delegate"].function(SimpleNamespace(deps=repeat_deps),Role.INVENTORY,"Repeat the already active Boss-to-Inventory edge")
        deps=AgentDeps(shared,Role.FACILITIES,(Role.FACILITIES,))
        ctx=SimpleNamespace(deps=deps)
        tools=team.agents[Role.FACILITIES]._function_toolset.tools
        with self.assertRaises(Exception):
            await tools["delegate"].function(ctx,Role.FACILITIES,"Create a cycle")
        with self.assertRaises(Exception):
            await tools["shop_tool"].function(ctx,"execute_approved_payment",{"request_id":1})
        with self.assertRaises(Exception):
            await tools["shop_tool"].function(ctx,"authorize_payment",{})
        shared.budget=RunBudget(max_total_tokens=24000)
        shared.usage.input_tokens=20000
        with self.assertRaises(RuntimeError):
            team._before_request(shared)

    async def test_five_agents_all_twenty_directed_edges_and_append_audit(self):
        budget=RunBudget(max_requests=100,max_total_tokens=100000,max_tool_calls=200)
        team=CampusTeam(budget,_test_models={r:scripted_model(r) for r in Role})
        # Exercise append-only history on a disposable audit file; preserve real runs.
        path=self.folder / "connectivity_audit.json"
        previous=json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        audit=AuditTrail(path)
        adapter=MCPAdapter(self.client)
        observed=set()
        for source in Role:
            shared=SharedRun(adapter,audit,budget)
            audit.append(shared.run_id,"offline_test_started",source,fixture="disposable copy; no production shop mutation; no model API")
            report=await team._run_role(source,"EXERCISE_ALL_PEERS",shared,(source,),None)
            self.assertEqual(report.role,source)
            history=json.loads(path.read_text(encoding="utf-8"))
            observed.update((entry["role"],entry["data"]["target"]) for entry in history if entry["run_id"]==shared.run_id and entry["event"]=="delegation")
        current=json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(current[:len(previous)],previous)
        self.assertEqual(len(observed),20)
        self.assertTrue(any(e["event"]=="loop_step_started" for e in current))
        self.assertTrue(any(e["event"]=="loop_step_finished" for e in current))
        self.assertNotIn("authorize_payment",AGENT_TOOLS)
        self.assertNotIn("confirm_purchase_order",AGENT_TOOLS)
        self.assertNotIn("receive_purchase_order",AGENT_TOOLS)

    async def test_live_cost_preflight_and_corrupt_audit(self):
        with self.assertRaises(RuntimeError):
            CampusTeam(RunBudget())
        path=self.folder / "corrupt.json"
        path.write_text("broken history",encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            AuditTrail(path).append("test","must_not_overwrite")
        self.assertEqual(path.read_text(),"broken history")
        self.assertEqual(MODEL_NAME,"gpt-6-luna")
        self.assertEqual(PORTKEY_BASE_URL,"https://api.portkey.ai/v1")

    async def test_selected_ticket_write_isolation(self):
        budget=RunBudget()
        team=CampusTeam(budget,_test_models={r:scripted_model(r) for r in Role})
        shared=SharedRun(MCPAdapter(self.client),AuditTrail(self.folder/'scope.json'),budget)
        deps=AgentDeps(shared,Role.BOSS,(Role.BOSS,),101)
        call=team.agents[Role.BOSS]._function_toolset.tools['shop_tool'].function
        with self.assertRaisesRegex(Exception,'assigned ticket_id'):
            await call(SimpleNamespace(deps=deps),'record_discount_decision',{'ticket_id':103,'unit_price':52,'rationale':'Wrong ticket'})
        self.assertEqual(shared.shop_calls,0)
        board=await call(SimpleNamespace(deps=deps),'read_shop_board',{})
        self.assertEqual(board['discount_decisions'],[])
        self.assertTrue(deps.read_evidence)
        shared.review_only=True
        with self.assertRaisesRegex(Exception,'read-only outcome review'):
            await call(SimpleNamespace(deps=deps),'fulfill_ticket_order',{'ticket_id':101})

    async def test_explicit_decline_does_not_spend_or_fulfill(self):
        before=await self.call('read_shop_board')
        draft=await self.call('save_board_draft',ticket_id=103,audience='customer',body='Draft: we cannot accept the 20-medium-hoodie request with the current stock and funding.')
        with self.assertRaises(Exception):
            await self.call('decline_ticket_request',ticket_id=101,rationale='Wrong type',customer_draft_id=draft['id'])
        with self.assertRaises(Exception):
            await self.call('decline_ticket_request',ticket_id=103,rationale='Stock shortfall',customer_draft_id=999)
        result=await self.call('decline_ticket_request',ticket_id=103,rationale='Insufficient stock and funding; no order fulfilled.',customer_draft_id=draft['id'])
        self.assertEqual(result['resolution']['outcome'],'declined')
        self.assertEqual(result['ticket']['status'],'resolved')
        after=await self.call('read_shop_board')
        self.assertEqual(after['inventory'],before['inventory'])
        self.assertEqual(after['cash_accounts'],before['cash_accounts'])
        self.assertEqual(after['payments'],[])
        with self.assertRaises(Exception):
            await self.call('fulfill_ticket_order',ticket_id=103)


if __name__=="__main__":
    logging.disable(logging.CRITICAL)  # Expected refusal cases are asserted below.
    databases=[ROOT / "data/campus_customs.db", ROOT / "data/campus_customs_new.db"]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in databases}
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(BusinessSafetyTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in databases}
    evidence={"test_mode":"offline deterministic protocol responders with real in-memory MCP on disposable database copies; no paid AI calls", "tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"production_databases_unchanged":before==after,"database_sha256_before":before,"database_sha256_after":after,"passed":result.wasSuccessful() and before==after}
    (ROOT / "output/problem5_checks.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")
    sys.exit(0 if evidence["passed"] else 1)
