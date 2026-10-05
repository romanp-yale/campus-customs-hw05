"""Five PydanticAI agents with bounded, fully connected delegation."""

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.usage import RunUsage, UsageLimits

from .audit import AuditTrail
from .config import ROOT, MODEL_NAME, build_model, budget_from_environment
from .mcp_client import AGENT_TOOLS, ShopMCP
from .models import AgentReport, Role, RunBudget

PROMPT_FILES = {Role.BOSS:"boss.md", Role.INVENTORY:"inventory.md", Role.ACCOUNTING:"accounting.md", Role.FACILITIES:"facilities.md", Role.CUSTOMER_SERVICE:"customer_service.md"}
READ_TOOLS = {"read_shop_board", "get_ticket_101_tee_order_context", "get_ticket_102_rent_context", "get_ticket_103_hoodie_discount_context"}
ROLE_WRITES = {
    Role.BOSS: {"record_discount_decision", "fulfill_ticket_order", "close_paid_rent_ticket", "decline_ticket_request"},
    Role.INVENTORY: {"draft_purchase_order"},
    Role.ACCOUNTING: {"request_payment", "draft_purchase_order"},
    Role.FACILITIES: set(),
    Role.CUSTOMER_SERVICE: {"save_board_draft"},
}


@dataclass
class SharedRun:
    shop: Any
    audit: AuditTrail
    budget: RunBudget
    run_id: str = field(default_factory=lambda: str(uuid4()))
    usage: RunUsage = field(default_factory=RunUsage)
    delegations: int = 0
    shop_calls: int = 0
    review_only: bool = False


@dataclass
class AgentDeps:
    shared: SharedRun
    role: Role
    path: tuple[Role, ...]
    ticket_id: int | None = None
    read_evidence: bool = False


class CampusTeam:
    def __init__(self, budget: RunBudget | None = None, *, _test_models: dict | None = None):
        self.budget = budget or budget_from_environment()
        self.test_mode = _test_models is not None
        if not self.test_mode and self.budget.input_usd_per_million is None:
            raise RuntimeError("Paid runs require verified price ceilings: CAMPUS_INPUT_USD_PER_MILLION and CAMPUS_OUTPUT_USD_PER_MILLION. No prices are assumed.")
        model = None if self.test_mode else build_model()
        self.agents = {role:self._make_agent(role, _test_models[role] if self.test_mode else model) for role in Role}

    def _make_agent(self, role, model):
        agent = Agent(model, name=role.value, deps_type=AgentDeps, output_type=AgentReport,
                      instructions=(ROOT / "backend/prompts" / PROMPT_FILES[role]).read_text(encoding="utf-8"),
                      retries=1, model_settings={"openai_reasoning_effort":"medium", "max_tokens":self.budget.max_output_per_request, "parallel_tool_calls":False, "timeout":30})

        @agent.tool(sequential=True)
        async def delegate(ctx: RunContext[AgentDeps], target: Role, task: str) -> dict:
            """Ask any other team role for a focused task. Never create a delegation
            repeated delegation edge or delegate human approval. A focused callback
            to the parent role is allowed. Shares the entire run's token budget.
            """
            deps=ctx.deps; shared=deps.shared
            active_edges=set(zip(deps.path,deps.path[1:]))
            if target==deps.role or (deps.role,target) in active_edges:
                raise ModelRetry("Self-delegation or a repeated active delegation edge is blocked; return evidence and blockers.")
            if len(deps.path)>shared.budget.max_depth or shared.delegations>=shared.budget.max_delegations:
                raise ModelRetry("Delegation budget reached; finish with evidence and explicit blockers.")
            if not task.strip() or len(task)>4000:
                raise ModelRetry("Delegation task must contain 1–4000 characters.")
            shared.delegations+=1
            shared.audit.append(shared.run_id,"delegation",role,target=target.value,task=task,path=[r.value for r in deps.path])
            report=await self._run_role(target,task,shared,deps.path+(target,),deps.ticket_id)
            return report.model_dump(mode="json")

        @agent.tool(sequential=True)
        async def shop_tool(ctx: RunContext[AgentDeps], tool_name: str, arguments: dict[str, Any]) -> Any:
            """Call a named Campus Customs MCP tool. Read tools: read_shop_board,
            get_ticket_101_tee_order_context, get_ticket_102_rent_context,
            get_ticket_103_hoodie_discount_context. All four read tools take
            arguments={} (never ticket_id). Writes are restricted by role:
            Boss: record_discount_decision(ticket_id,unit_price,rationale),
            fulfill_ticket_order(ticket_id), close_paid_rent_ticket(ticket_id).
            decline_ticket_request(ticket_id,rationale,customer_draft_id) closes
            a price-override request as declined, never as fulfilled.
            Inventory/Accounting: draft_purchase_order(ticket_id,vendor_id,qty).
            Accounting: request_payment(ticket_id,kind,account,purchase_order_id).
            Customer Service:
            save_board_draft(ticket_id,audience,body), audience exactly
            'customer' or 'vendor', body 1–8000 characters. No human approval tool.
            """
            deps=ctx.deps; shared=deps.shared
            if shared.review_only and tool_name not in READ_TOOLS:
                raise ModelRetry('This is a read-only outcome review; no mutation is permitted.')
            if tool_name not in READ_TOOLS and deps.ticket_id is not None and arguments.get('ticket_id') != deps.ticket_id:
                raise ModelRetry('Writes must target the assigned ticket_id; other tickets may only be read for shared constraints.')
            if tool_name not in READ_TOOLS | ROLE_WRITES[role] or tool_name not in AGENT_TOOLS:
                shared.audit.append(shared.run_id,"tool_denied",role,tool_name=tool_name)
                raise ModelRetry("This role cannot call that tool. Delegate to the appropriate role.")
            shared.shop_calls+=1
            if shared.shop_calls>shared.budget.max_tool_calls:
                raise RuntimeError("Shared MCP call budget exhausted.")
            shared.audit.append(shared.run_id,"mcp_call",role,tool_name=tool_name,arguments=arguments)
            try:
                result=await shared.shop.call(tool_name,arguments)
            except Exception as exc:
                shared.audit.append(shared.run_id,"mcp_error",role,tool_name=tool_name,error_type=type(exc).__name__,error=str(exc))
                raise ModelRetry(f"MCP refused the operation: {exc}") from exc
            shared.audit.append(shared.run_id,"mcp_result",role,tool_name=tool_name,result=result)
            if tool_name in READ_TOOLS:
                deps.read_evidence=True
            return result

        @agent.output_validator
        def validate_report(ctx: RunContext[AgentDeps], report: AgentReport):
            if report.role!=role:
                raise ModelRetry("Report role must match the currently running agent.")
            if not ctx.deps.read_evidence:
                raise ModelRetry("Read live shop evidence through MCP before completing your report.")
            if ctx.deps.ticket_id is not None and report.ticket_id!=ctx.deps.ticket_id:
                raise ModelRetry("Report ticket_id must match the assigned ticket.")
            return report

        return agent

    def _cost(self, shared):
        b=shared.budget
        if b.input_usd_per_million is None:
            return None
        return (Decimal(shared.usage.input_tokens)*b.input_usd_per_million + Decimal(shared.usage.output_tokens)*b.output_usd_per_million)/Decimal(1000000)

    def _before_request(self, shared):
        b=shared.budget
        # Reserve a full next request before issuing it; count_tokens_before_request
        # separately enforces the input ceiling with PydanticAI's token estimator.
        reserve=b.max_input_per_request+b.max_output_per_request
        if shared.usage.total_tokens+reserve>b.max_total_tokens:
            raise RuntimeError("Insufficient remaining shared token budget for another request.")
        spent=self._cost(shared)
        if spent is not None:
            next_cost=(Decimal(b.max_input_per_request)*b.input_usd_per_million + Decimal(b.max_output_per_request)*b.output_usd_per_million)/Decimal(1000000)
            if spent+next_cost>b.max_estimated_cost_usd:
                raise RuntimeError("Estimated cost budget exhausted before next model request.")

    async def _run_role(self, role, prompt, shared, path, ticket_id):
        deps=AgentDeps(shared,role,path,ticket_id)
        b=shared.budget
        limits=UsageLimits(request_limit=b.max_requests,total_tokens_limit=b.max_total_tokens,
                           tool_calls_limit=b.max_tool_calls,per_request_input_tokens_limit=b.max_input_per_request,
                           count_tokens_before_request=not self.test_mode)
        shared.audit.append(shared.run_id,"agent_started",role,prompt=prompt,ticket_id=ticket_id)
        try:
            async with self.agents[role].iter(prompt,deps=deps,usage=shared.usage,usage_limits=limits) as run:
                node=run.next_node
                message_count=0
                while not Agent.is_end_node(node):
                    name=type(node).__name__
                    shared.audit.append(shared.run_id,"loop_step_started",role,node=name,usage=self._usage(shared))
                    if Agent.is_model_request_node(node):
                        self._before_request(shared)
                    node=await run.next(node)
                    messages=run.all_messages()
                    new_messages=ModelMessagesTypeAdapter.dump_python(messages[message_count:],mode="json")
                    message_count=len(messages)
                    shared.audit.append(shared.run_id,"loop_step_finished",role,node=name,messages=new_messages,usage=self._usage(shared))
                    cost=self._cost(shared)
                    if cost is not None and cost>b.max_estimated_cost_usd:
                        raise RuntimeError("Estimated cost ceiling exceeded; stopping the run.")
                report=run.result.output
                shared.audit.append(shared.run_id,"agent_finished",role,report=report.model_dump(mode="json"),usage=self._usage(shared))
                return report
        except BaseException as exc:
            shared.audit.append(shared.run_id,"agent_failed",role,error_type=type(exc).__name__,usage=self._usage(shared))
            raise

    def _usage(self, shared):
        return {"requests":shared.usage.requests,"input_tokens":shared.usage.input_tokens,
                "output_tokens":shared.usage.output_tokens,"total_tokens":shared.usage.total_tokens,
                "tool_calls":shared.usage.tool_calls,"estimated_cost_usd":str(self._cost(shared)) if self._cost(shared) is not None else None}

    async def run(self, prompt: str, ticket_id: int | None = None, *, _shop=None, _audit=None, run_id=None, review_only=False):
        audit=_audit or AuditTrail(ROOT / "output/audit_trail.json")
        if ticket_id is not None and ticket_id not in (101,102,103):
            raise ValueError("Choose ticket 101, 102, or 103.")
        async def execute(shop):
            shared=SharedRun(shop,audit,self.budget)
            shared.review_only=review_only
            if run_id is not None:
                shared.run_id=run_id
            audit.append(shared.run_id,"team_started",model=MODEL_NAME if not self.test_mode else "offline-test",budget=self.budget.model_dump(mode="json"))
            try:
                async with asyncio.timeout(self.budget.timeout_seconds):
                    task=f"Assigned ticket: {ticket_id if ticket_id is not None else 'all open tickets'}.\n{prompt}"
                    if review_only:
                        task='READ-ONLY REVIEW: verify the stored outcome and report it; all writes are disabled.\n'+task
                    report=await self._run_role(Role.BOSS,task,shared,(Role.BOSS,),ticket_id)
                    board=await shop.call("read_shop_board",{})
                    audit.append(shared.run_id,"resolution_check",Role.BOSS,board=board)
                    if report.outcome=="resolved":
                        relevant=[t for t in board["tickets"] if ticket_id is None or t["id"]==ticket_id]
                        if not relevant or any(t["status"]!="resolved" for t in relevant):
                            raise RuntimeError("Agent claimed resolution without matching MCP ticket state.")
                    audit.append(shared.run_id,"team_finished",report=report.model_dump(mode="json"),usage=self._usage(shared))
                    return {"run_id":shared.run_id,"report":report.model_dump(mode="json"),"usage":self._usage(shared),"board":board}
            except BaseException as exc:
                audit.append(shared.run_id,"team_failed",error_type=type(exc).__name__,usage=self._usage(shared))
                raise
        if _shop is not None:
            return await execute(_shop)
        async with ShopMCP() as shop:
            return await execute(shop)
