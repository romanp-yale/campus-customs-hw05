from pathlib import Path
root = Path(__file__).resolve().parent.parent
for name in ['frontend/src/App.tsx', 'AI_prompts.md', 'mcp_server/README.md']:
    p = root / name
    raw = p.read_bytes().decode('utf-8', errors='surrogateescape')
    text = ''.join(bytes([ord(c)-0xdc00]).decode('cp1252') if 0xdc80 <= ord(c) <= 0xdcff else c for c in raw)
    p.write_text(text, encoding='utf-8')
