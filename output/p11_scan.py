"""Scan the Git index without printing secret values."""
from pathlib import Path
import subprocess,re,json,hashlib
r=Path(__file__).resolve().parent.parent
g=['git','-c','safe.directory='+str(r),'-C',str(r)]
names=[n for n in subprocess.check_output(g+['ls-files','-z']).decode().split('\0') if n]
secrets=[]
for p in [r/'.env',r.parent.parent/'.env']:
 if p.exists():
  for line in p.read_text(encoding='utf-8').splitlines():
   m=re.match(r'\s*([\w]+)\s*=\s*(.+)',line)
   if m and any(w in m[1].upper() for w in ['KEY','TOKEN','SECRET','PASSWORD']):
    v=m[2].strip().strip(chr(34)+chr(39))
    if len(v)>=8:secrets.append(v.encode())
issues=[]
for n in names:
 data=subprocess.check_output(g+['show',':'+n])
 if any(v in data for v in secrets):issues.append({'file':n,'reason':'local secret value'})
 if re.search(rb'(?<![A-Za-z0-9_-])(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)',data):issues.append({'file':n,'reason':'credential pattern'})
assert not issues,issues
assert '.env' not in names
required=['requirements.txt','.env.example','.mcp.json','.gitignore','README.md','AI_prompts.md','data/campus_customs.db','data/campus_customs_new.db','backend/main.py','backend/models.py','mcp_server/server.py','mcp_server/README.md','frontend/package.json']+['backend/prompts/'+x+'.md' for x in ['boss','inventory','accounting','facilities','customer_service']]+['output/'+x for x in ['harness.md','mcp_smoke.json','desk_tickets.html','design.md','resolved_tickets.json','resolved_board.html','audit_trail.json','github_url.txt']]
assert all(n in names for n in required),set(required)-set(names)
assert hashlib.sha256((r/'data/campus_customs.db').read_bytes()).hexdigest()=='23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a'
result={'staged_files_scanned':len(names),'local_secret_values_and_credential_patterns_absent':True,'real_env_excluded':True,'required_files_present':True,'both_databases_included':True,'original_hash_preserved':True,'false_positive_review':'Embedded sk- substring inside opaque model response signature; not a credential token.'}
(r/'output/p11_submission_check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
