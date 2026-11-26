import json, subprocess, sys, os

SERVER = os.path.expanduser("~/projects/fanqie-rank-scout/fanqie_rank_mcp.py")
reqs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    {"jsonrpc": "2.0", "id": 3, "method": "ping"},
    {"jsonrpc": "2.0", "id": 4, "method": "resources/list"},
    {"jsonrpc": "2.0", "id": 5, "method": "bogus/method"},
]
inp = "\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n"
p = subprocess.run([sys.executable, SERVER], input=inp, capture_output=True, text=True, timeout=120)
print("exit:", p.returncode)
for line in p.stdout.splitlines():
    o = json.loads(line)
    if o.get("id") == 2:
        print("tools:", [t["name"] for t in o["result"]["tools"]])
        for t in o["result"]["tools"]:
            print("   ", t["name"], "required=", t["inputSchema"].get("required"), "hasOutputSchema=", "outputSchema" in t)
    elif o.get("id") == 1:
        print("init:", o["result"]["protocolVersion"], o["result"]["serverInfo"]["name"], "caps=", list(o["result"]["capabilities"]))
    else:
        print("id", o.get("id"), "->", json.dumps(o.get("result", o.get("error")), ensure_ascii=False)[:100])
print("stderr:", p.stderr.strip()[:300])
