import json, subprocess, sys, os, time

SERVER = os.path.expanduser("~/projects/fanqie-rank-scout/fanqie_rank_mcp.py")
reqs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "list_categories", "arguments": {"board": "male-new"}}},
    {"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "rank_list", "arguments": {"board": "male-new", "category": "都市脑洞", "limit": 5}}},
    {"jsonrpc": "2.0", "id": 12, "method": "tools/call", "params": {"name": "rank_list", "arguments": {"category": "不存在的分类"}}},
    {"jsonrpc": "2.0", "id": 13, "method": "tools/call", "params": {"name": "rank_list", "arguments": {"board": "male-read", "category": "悬疑灵异", "limit": 3}}},
]
inp = "\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n"
t0 = time.time()
p = subprocess.run([sys.executable, SERVER], input=inp, capture_output=True, text=True, timeout=300)
print("exit:", p.returncode, "elapsed: %.1fs" % (time.time() - t0))
for line in p.stdout.splitlines():
    o = json.loads(line)
    i = o.get("id")
    if i == 10:
        sc = o["result"]["structuredContent"]
        print("\n[id10 list_categories] count=%d board=%s" % (len(sc["categories"]), sc["board"]))
        print("  前 12 个:", "、".join(c["category"] for c in sc["categories"][:12]))
        print("  text:", o["result"]["content"][0]["text"][:120])
    elif i == 11:
        sc = o["result"]["structuredContent"]
        print("\n[id11 rank_list 都市脑洞 x5] count=%d" % sc["count"])
        print(o["result"]["content"][0]["text"])
        r0 = sc["rows"][0]
        print("  structured row0 keys:", sorted(k for k in r0 if r0[k] is not None))
        print("  row0:", r0["title"], r0["author"], r0["read_text"], "wc=", r0.get("word_count_wan"), "ratio=", r0.get("ratio"))
    elif i == 12:
        print("\n[id12 bad category] isError=", o["result"].get("isError"), "|", o["result"]["content"][0]["text"][:160])
    elif i == 13:
        sc = o["result"]["structuredContent"]
        print("\n[id13 male-read 悬疑灵异 x3] count=%d err=%s" % (sc.get("count", -1), o["result"].get("isError")))
        print(o["result"]["content"][0]["text"][:600])
print("\nstderr:", p.stderr.strip()[:300])
