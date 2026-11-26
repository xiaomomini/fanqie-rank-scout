"""通用探针：把 argv 当成 MCP server 命令，跑一遍握手 + 一个真实工具调用。

用法： python3 tests/probe_any.py <命令...>
例：   python3 tests/probe_any.py uvx --from git+https://github.com/xiaomomini/fanqie-rank-scout fanqie-rank-mcp
"""
import json
import subprocess
import sys
import time


def main(argv):
    if not argv:
        print("需要命令")
        return 2
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "probe", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "rank_list", "arguments": {"board": "male-new", "category": "都市脑洞", "limit": 2}}},
    ]
    inp = "\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n"
    t0 = time.time()
    p = subprocess.run(argv, input=inp, capture_output=True, text=True, timeout=300)
    print("cmd:", " ".join(argv))
    print("exit:", p.returncode, "elapsed: %.1fs" % (time.time() - t0))
    saw = []
    for line in p.stdout.splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            print("  [非 JSON stdout] %r" % line[:120])
            continue
        saw.append(o.get("id"))
        if o.get("id") == 1:
            r = o["result"]
            print("  initialize ok:", r["protocolVersion"], r["serverInfo"]["name"], r["serverInfo"]["version"])
        elif o.get("id") == 2:
            print("  tools:", [t["name"] for t in o["result"]["tools"]])
        elif o.get("id") == 3:
            res = o["result"]
            print("  tools/call isError:", res.get("isError"))
            print("  " + res["content"][0]["text"].replace("\n", "\n  ")[:500])
    print("  responses:", saw)
    err = (p.stderr or "").strip().splitlines()
    print("  stderr tail:", err[-2:] if err else "(empty)")
    return 0 if saw[:3] == [1, 2, 3] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
