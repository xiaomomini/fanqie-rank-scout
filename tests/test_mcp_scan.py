"""端到端跑一次 scan_categories（最慢的工具），验证耗时与结果。"""
import json
import os
import subprocess
import sys
import time

SERVER = os.path.expanduser("~/projects/fanqie-rank-scout/fanqie_rank_mcp.py")
reqs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
     "params": {"name": "scan_categories", "arguments": {"board": "male-new", "top": 5}}},
]
inp = "\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n"
t0 = time.time()
p = subprocess.run([sys.executable, SERVER], input=inp, capture_output=True, text=True, timeout=300)
elapsed = time.time() - t0
for line in p.stdout.splitlines():
    o = json.loads(line)
    if o.get("id") == 2:
        res = o["result"]
        print("isError:", res.get("isError"), "| 耗时 %.1fs" % elapsed)
        print(res["content"][0]["text"])
        sc = res.get("structuredContent") or {}
        print("rows:", len(sc.get("rows", [])), "| top row:", json.dumps(sc.get("rows", [{}])[0], ensure_ascii=False)[:200])
