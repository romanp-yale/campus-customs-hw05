"""Read-only verification of the current P9 evidence snapshot."""
from pathlib import Path
import hashlib
import json
import re
import sqlite3

out = Path(__file__).resolve().parent
root = out.parent
evidence = json.loads((out / 'resolved_tickets.json').read_text(encoding='utf-8'))
original_hash = hashlib.sha256((root / 'data/campus_customs.db').read_bytes()).hexdigest()
assert original_hash == '23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a'
expected = re.findall(r'<section class="expected".*?</section>', (out / 'desk_tickets.html').read_text(encoding='utf-8'), re.S)
baseline = json.loads((out / 'p9_expected_hashes.json').read_text(encoding='utf-8-sig'))
hashes = [hashlib.sha256(s.encode()).hexdigest() for s in expected]
windows_hashes = [hashlib.sha256(s.replace('\n', '\r\n').encode()).hexdigest() for s in expected]
variants = {
    'utf8': hashes,
    'crlf': windows_hashes,
    'stripped': [hashlib.sha256(s.strip().encode()).hexdigest() for s in expected],
    'windows-decoded': [hashlib.sha256(s.encode().decode('cp1252').encode()).hexdigest() for s in expected],
}
assert any(h == baseline for h in variants.values()), variants
with sqlite3.connect((root / 'data/campus_customs_new.db').as_uri() + '?mode=ro', uri=True) as db:
    balance = db.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
    statuses = db.execute('SELECT id,status FROM tickets ORDER BY id').fetchall()
assert str(balance) == evidence['ending_checking_balance']
assert statuses == [(t['ticket_id'], t['final_status']) for t in evidence['tickets']]
result = {'original_unchanged': True, 'expected_sections_unchanged': True, 'checking_matches_sqlite': True, 'checking_balance': balance, 'ticket_statuses': statuses, 'complete': evidence['complete']}
(out / 'p9_verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
