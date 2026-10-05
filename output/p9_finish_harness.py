from pathlib import Path

path = Path(__file__).with_name('harness.md')
raw = path.read_bytes().decode('utf-8', errors='surrogateescape')
text = ''.join(bytes([ord(c)-0xdc00]).decode('cp1252') if 0xdc80 <= ord(c) <= 0xdcff else c for c in raw)
addition = '''

### Problem 9 actual evidence and remaining human decisions

The reset is recorded at audit sequence 1821. Real dashboard runs were made for all three tickets using gpt-6-luna through Portkey. The audit retains the failed provider preflight, Windows audit-write race, and request-limit attempt as well as subsequent real agent actions. Windows audit replacement now retries transient file contention, and activity reads share the audit lock. Four isolated backend integration tests passed after these runtime fixes (output/p9_runtime_checks.log).

- Ticket 101: Boss, Inventory, and Accounting investigated stock and invoice 501. Accounting prepared pending payment request #1 for $840; Inventory prepared one small white tee as purchase draft #1. The run exhausted its request cap and did not complete a final Boss report. No supplier quote, invoice coverage, stock receipt, payment, or fulfillment has been asserted.
- Ticket 102: Boss contacted Facilities, which delegated to Accounting. Accounting prepared pending rent payment request #2 for $2,400. The completed run returned awaiting_human. It used 10 requests and 17,103 provider-reported tokens, with a conservative estimated model cost of $0.0067325.
- Ticket 103: Boss contacted Inventory first; Inventory delegated financial analysis to Accounting. Boss separately requested an unsent draft from Customer Service. The completed run returned awaiting_human. Boss recorded a proposed $52 unit price, explicitly without customer acceptance, and a customer draft was saved. Exact medium stock remains 8 against a 20-unit request. It used 20 requests and 45,542 provider-reported tokens, with a conservative estimated model cost of $0.0178346. The earlier customer draft predates the Boss's price proposal and therefore states that no price has yet been approved; this historical draft is preserved as actual evidence.

Current cash reconciliation: $3,400.00 starting balance minus $0.00 recorded payments equals $3,400.00, exactly matching cash_accounts in a separate read-only SQLite verification. Original database SHA-256 is unchanged. Expected sections are preserved; their baseline hashes were originally computed using Windows cp1252 decoding, which the verifier accounts for without changing their text. Evidence: output/p9_verification.json and output/resolved_tickets.json.

Human payment approval is still required for the two prepared requests. Paying both would leave $160.00. Twelve additional hoodies at the stored $22 planning cost would require $264.00, a $104.00 deficit; no revenue or artificial cash increase is allowed. A confirmed supplier quote and actual receipt are also needed before asserting tee stock. The human has been asked whether the hoodie request should be declined or remain blocked while a valid supplier/funding alternative is provided. No decision has been inferred from silence.

output/desk_tickets.html now contains real Actual agents, delegations, tools, reports, and current cash while retaining Expected sections. output/resolved_tickets.json explicitly reports complete=false and all stored statuses open. output/resolved_board.html is an evidence page with clearly labeled pending captures; resolved-ticket screenshots will only be embedded after the corresponding database statuses really become resolved. The live dashboard remains available for human review. These files document progress honestly and do not claim that Problem 9 is finished.
'''
if '### Problem 9 actual evidence and remaining human decisions' not in text:
    text += addition
path.write_text(text, encoding='utf-8')
print('Harness updated with actual evidence and pending human decisions.')
