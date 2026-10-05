"""Shared agent, budget, and audit data types; no database access."""

from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class Role(str, Enum):
    BOSS = "Boss"
    INVENTORY = "Inventory"
    ACCOUNTING = "Accounting"
    FACILITIES = "Facilities"
    CUSTOMER_SERVICE = "Customer Service"


class AgentReport(BaseModel):
    role: Role
    ticket_id: int | None = None
    outcome: Literal["investigated", "awaiting_human", "blocked", "resolved"]
    summary: str = Field(min_length=1, max_length=6000)
    evidence: list[str] = Field(default_factory=list, max_length=20)
    next_actions: list[str] = Field(default_factory=list, max_length=12)


class RunBudget(BaseModel):
    max_requests: int = Field(default=24, ge=1, le=100)
    max_total_tokens: int = Field(default=80000, ge=1000, le=100000)
    max_input_per_request: int = Field(default=16000, ge=1000, le=32000)
    max_output_per_request: int = Field(default=1600, ge=128, le=4000)
    max_tool_calls: int = Field(default=60, ge=1, le=200)
    max_delegations: int = Field(default=12, ge=1, le=30)
    max_depth: int = Field(default=4, ge=1, le=4)
    timeout_seconds: int = Field(default=180, ge=10, le=600)
    max_estimated_cost_usd: Decimal = Field(default=Decimal("1.00"), gt=0, le=10)
    input_usd_per_million: Decimal | None = Field(default=None, gt=0)
    output_usd_per_million: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def paired_rates(self):
        if (self.input_usd_per_million is None) != (self.output_usd_per_million is None):
            raise ValueError("Configure both input and output price ceilings, or neither.")
        return self


class AuditEntry(BaseModel):
    sequence: int
    recorded_at_utc: str
    run_id: str
    event: str
    role: Role | None = None
    data: dict[str, Any] = Field(default_factory=dict)


# Dashboard request types. No database facts or credentials supplied by agents.
class RunRequest(BaseModel):
    prompt: str = Field(default='Resolve the selected ticket safely; stop when human input is required.', min_length=1, max_length=8000)
    review_only: StrictBool = False


class HumanDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    approved: StrictBool
    approved_by: str = Field(min_length=1, max_length=120)


class PurchaseDecision(HumanDecision):
    confirmed_unit_cost: float = Field(gt=0, allow_inf_nan=False)
    covered_by_paid_invoice: StrictBool = False
    simulation_note: str | None = Field(default=None, min_length=1, max_length=1000)


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    approved_by: str = Field(min_length=1, max_length=120)
    confirm: StrictBool


class ReceiptDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    approved_by: str = Field(min_length=1, max_length=120)
    received_qty: int = Field(strict=True, gt=0)
    confirm: StrictBool
    simulation_note: str | None = Field(default=None, min_length=1, max_length=1000)


