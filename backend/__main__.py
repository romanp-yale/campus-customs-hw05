"""Local team runner and human-only payment approval command."""

import argparse
import asyncio
import json
import os
from uuid import uuid4

from .audit import AuditTrail
from .config import ROOT, load_environment
from .mcp_client import ShopMCP


async def main():
    parser=argparse.ArgumentParser(description="Campus Customs multi-agent backend")
    sub=parser.add_subparsers(dest="command",required=True)
    run=sub.add_parser("run")
    run.add_argument("prompt")
    run.add_argument("--ticket",type=int,choices=(101,102,103))
    approve=sub.add_parser("approve-payment",help="Human-only review; never invoke from an agent")
    approve.add_argument("request_id",type=int)
    approve.add_argument("--name",required=True)
    confirm=sub.add_parser("confirm-purchase",help="Human supplier/quote attestation")
    confirm.add_argument("purchase_order_id",type=int)
    confirm.add_argument("--unit-cost",type=float,required=True)
    confirm.add_argument("--name",required=True)
    confirm.add_argument("--covered-by-paid-invoice",action="store_true",help="Human attests the goods are already funded by this ticket's paid linked invoice")
    receive=sub.add_parser("receive-purchase",help="Human physical receipt attestation")
    receive.add_argument("purchase_order_id",type=int)
    receive.add_argument("--qty",type=int,required=True)
    receive.add_argument("--name",required=True)
    args=parser.parse_args()
    load_environment()
    if args.command=="run":
        from .team import CampusTeam
        result=await CampusTeam().run(args.prompt,args.ticket)
    else:
        async with ShopMCP(human=True) as shop:
            board=await shop.call("read_shop_board",{})
            is_payment=args.command=="approve-payment"
            table="approval_requests" if is_payment else "purchase_order_drafts"
            reference=args.request_id if is_payment else args.purchase_order_id
            matches=[r for r in board[table] if r["id"]==reference]
            if not matches:
                raise ValueError("Requested record not found.")
            print(json.dumps(matches[0],indent=2))
            common={"approved_by":args.name,"approval_secret":os.environ["CAMPUS_HUMAN_APPROVAL_KEY"]}
            if is_payment:
                approved=input("Approve this exact payment? Type APPROVE, or REJECT: ").strip()
                if approved not in ("APPROVE","REJECT"):
                    raise ValueError("No approval recorded; explicit choice required.")
                name="authorize_payment"
                arguments={"request_id":reference,"approved":approved=="APPROVE",**common}
            elif args.command=="confirm-purchase":
                print(f"Attest the supplier is suitable and its confirmed unit cost is {args.unit_cost}.")
                if args.covered_by_paid_invoice:
                    print("Also attest that these goods are already covered by the ticket's paid linked invoice; no second purchase charge.")
                if input("Type CONFIRM to attest these real facts: ").strip()!="CONFIRM":
                    raise ValueError("No confirmation recorded.")
                name="confirm_purchase_order"
                arguments={"purchase_order_id":reference,"confirmed_unit_cost":args.unit_cost,"covered_by_paid_invoice":args.covered_by_paid_invoice,**common}
            else:
                print(f"Attest that {args.qty} additional units were physically received.")
                if input("Type RECEIVED to attest the physical receipt: ").strip()!="RECEIVED":
                    raise ValueError("No receipt recorded.")
                name="receive_purchase_order"
                arguments={"purchase_order_id":reference,"received_qty":args.qty,**common}
            result=await shop.call(name,arguments)
            AuditTrail(ROOT / "output/audit_trail.json").append(str(uuid4()),"human_action",tool_name=name,reference_id=reference,result=result)
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=="__main__":
    asyncio.run(main())
