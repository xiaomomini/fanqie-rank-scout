#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fanqie-rank-scout 的 MCP Server（stdio，JSON-RPC 2.0，零依赖）。

给 Claude Desktop / Cursor / Cline / Continue 等 MCP 客户端用：
把「番茄公开榜单」变成模型可以自己调用的三个工具。

    python3 fanqie_rank_mcp.py            # 直接跑（客户端会拉起它）
    uvx --from git+https://github.com/xiaomomini/fanqie-rank-scout fanqie-rank-mcp

协议：MCP 2025-06-18 / 2025-03-26 / 2024-11-05，stdio 传输，一行一个 JSON。
stdout 只允许出现 JSON-RPC 消息，日志一律走 stderr。
"""

import json
import sys
import time

from fanqie_rank_scout import (
    BASE,
    BOARDS,
    PUA_RE,
    http_get,
    parse_menu,
    parse_rank,
    parse_read_count,
    resolve_book,
)

SERVER_NAME = "fanqie-rank-scout"
SERVER_VERSION = "1.1.0"
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_BOARD = "male-new"
DEFAULT_CATEGORY = "都市脑洞"

_MENU = {"ts": 0.0, "data": {}}
_MENU_TTL = 6 * 3600  # 导航菜单一天只变一次，缓存久一点省钱省时


def log(msg):
    sys.stderr.write("[fanqie-rank-mcp] %s\n" % msg)
    sys.stderr.flush()


def get_menu(force=False):
    """取榜单导航 {板块中文名: {分类名: rank 路径}}，带 6 小时内存缓存。"""
    now = time.time()
    if not force and _MENU["data"] and now - _MENU["ts"] < _MENU_TTL:
        return _MENU["data"]
    html = http_get("%s/rank/%s" % (BASE, "1_2_262"))  # 任意榜单页都含完整导航
    menu = parse_menu(html)
    if menu:
        _MENU["data"] = menu
        _MENU["ts"] = now
    return _MENU["data"]


def _shape_rows(items, board_name, category, resolve=True):
    """把 parse_rank 的原始行补成带 read_num / ratio 的结构。"""
    if resolve:
        def enrich(row):
            try:
                info = resolve_book(row["book_id"])
            except Exception:  # 单本失败不影响整表
                return row
            row["title"] = info.get("title") or row["title"]
            row["author"] = info.get("author") or row["author"]
            row["word_count_wan"] = info.get("word_count_wan")
            return row

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            items = list(pool.map(enrich, items))

    rows = []
    for r in items:
        r["read_num"] = parse_read_count(r.get("read_text"))
        wc = r.get("word_count_wan")
        r["ratio"] = round(r["read_num"] / 10000.0 / wc, 2) if (r["read_num"] and wc) else None
        r["board"] = board_name
        r["category"] = category
        if PUA_RE.search(r.get("title") or ""):
            r["title"] = PUA_RE.sub("□", r["title"])
        rows.append(r)
    return rows


def _md_table(rows):
    out = ["| 排名 | 书名 | 作者 | 在读 | 字数(万) | 在读/万字 | 状态 | 链接 |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r.get("rank", ""), r.get("title", ""), r.get("author", ""),
            r.get("read_text", ""),
            r.get("word_count_wan") if r.get("word_count_wan") is not None else "-",
            r.get("ratio") if r.get("ratio") is not None else "-",
            r.get("status", ""), r.get("url", "")))
    return "\n".join(out)


# ---------------------------------------------------------------- 工具实现

def tool_rank_list(args):
    board = args.get("board") or DEFAULT_BOARD
    if board not in BOARDS:
        raise ValueError("board 必须是 %s 之一" % "/".join(sorted(BOARDS)))
    category = (args.get("category") or DEFAULT_CATEGORY).strip()
    limit = max(1, min(int(args.get("limit") or 10), 10))
    resolve = args.get("resolve", True)

    menu = get_menu()
    cats = menu.get(BOARDS[board], {})
    if not cats:
        menu = get_menu(force=True)
        cats = menu.get(BOARDS[board], {})
    if category not in cats:
        raise ValueError("分类 %r 不在%s里。可用：%s"
                         % (category, BOARDS[board], "、".join(cats) or "（导航解析失败）"))
    html = http_get("%s/rank/%s" % (BASE, cats[category]))
    rows = _shape_rows(parse_rank(html)[:limit], BOARDS[board], category, resolve)

    head = "榜单：%s · %s（前 %d，共 %d 条）\n" % (BOARDS[board], category, len(rows), len(rows))
    text = head + _md_table(rows)
    return text, {"board": board, "category": category, "count": len(rows), "rows": rows}


def tool_list_categories(args):
    board = args.get("board") or DEFAULT_BOARD
    if board not in BOARDS:
        raise ValueError("board 必须是 %s 之一" % "/".join(sorted(BOARDS)))
    menu = get_menu()
    cats = menu.get(BOARDS[board], {})
    if not cats:
        cats = get_menu(force=True).get(BOARDS[board], {})
    items = [{"category": name, "rank_path": path} for name, path in cats.items()]
    text = "%s（%d 个分类）：%s" % (BOARDS[board], len(items), "、".join(i["category"] for i in items))
    return text, {"board": board, "categories": items}


def tool_scan(args):
    """扫一个板块的全部分类，按前 10 在读中位数排序 —— 找还有流量的分类。"""
    import statistics
    board = args.get("board") or DEFAULT_BOARD
    if board not in BOARDS:
        raise ValueError("board 必须是 %s 之一" % "/".join(sorted(BOARDS)))
    top_n = max(1, min(int(args.get("top") or 10), 40))

    menu = get_menu()
    cats = menu.get(BOARDS[board], {})
    if not cats:
        cats = get_menu(force=True).get(BOARDS[board], {})
    if not cats:
        raise RuntimeError("导航解析失败，番茄榜单结构可能改了")

    rows = []
    for name, path in cats.items():
        try:
            items = parse_rank(http_get("%s/rank/%s" % (BASE, path)))
        except Exception as exc:
            log("skip %s: %s" % (name, exc))
            continue
        reads = [x for x in (parse_read_count(i["read_text"]) for i in items) if x]
        if not items or not reads:
            continue
        rows.append({
            "category": name,
            "rank_path": path,
            "top_book_id": items[0].get("book_id"),
            "top_title": PUA_RE.sub("□", items[0].get("title") or ""),
            "top_read": reads[0],
            "median_read": int(statistics.median(reads)),
            "sum_read": sum(reads),
        })
        time.sleep(0.3)

    rows.sort(key=lambda r: r["median_read"], reverse=True)
    rows = rows[:top_n]

    # 榜单页书名有字体混淆，只给返回的这几行反查详情页（3-10 次请求，并行）
    def fix_title(row):
        if not row.get("top_book_id"):
            return row
        try:
            row["top_title"] = resolve_book(row["top_book_id"]).get("title") or row["top_title"]
        except Exception:
            pass
        return row

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(fix_title, rows))

    out = ["| 分类 | 在读中位 | 前10合计 | 榜一 | 榜一在读 |",
           "|---|---|---|---|---|"]
    for r in rows:
        out.append("| %s | %.1f万 | %.1f万 | %s | %.1f万 |" % (
            r["category"], r["median_read"] / 10000.0, r["sum_read"] / 10000.0,
            r["top_title"], r["top_read"] / 10000.0))
    text = "%s · 按前 10 在读中位数排序（%d 个分类）\n%s" % (BOARDS[board], len(rows), "\n".join(out))
    return text, {"board": board, "count": len(rows), "rows": rows}


TOOLS = [
    {
        "name": "rank_list",
        "title": "番茄榜单明细",
        "description": ("抓番茄小说公开榜单某一分类的前 10 本，返回书名/作者/在读/字数/在读密度。"
                        "用来判断某个题材现在谁在榜上、读者还剩多少。无需登录。"),
        "inputSchema": {
            "type": "object",
            "properties": {
                "board": {"type": "string", "enum": sorted(BOARDS), "default": DEFAULT_BOARD,
                          "description": "榜单：male-read 男频阅读榜 / male-new 男频新书榜 / "
                                         "female-read 女频阅读榜 / female-new 女频新书榜"},
                "category": {"type": "string", "default": DEFAULT_CATEGORY,
                             "description": "分类名，如 都市脑洞、悬疑脑洞、都市高武（先调 list_categories 取全量）"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 10,
                          "description": "条数，榜单页只展示前 10"},
                "resolve": {"type": "boolean", "default": True,
                            "description": "是否反查书籍详情页拿干净书名/字数（慢几秒，但榜单页书名有字体混淆）"},
            },
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "board": {"type": "string"}, "category": {"type": "string"},
                "count": {"type": "integer"},
                "rows": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["rows"],
        },
    },
    {
        "name": "list_categories",
        "title": "榜单分类列表",
        "description": "列出某个板块下所有可查的分类名（番茄每个榜单有几十个分类）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "board": {"type": "string", "enum": sorted(BOARDS), "default": DEFAULT_BOARD},
            },
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "board": {"type": "string"},
                "categories": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["categories"],
        },
    },
    {
        "name": "scan_categories",
        "title": "分类热度扫描",
        "description": ("扫一个板块的全部分类，按「前 10 在读中位数」排序，回答「现在哪个分类还有人看」。"
                        "一次请求几十个榜单页，约 30-50 秒。"),
        "inputSchema": {
            "type": "object",
            "properties": {
                "board": {"type": "string", "enum": sorted(BOARDS), "default": DEFAULT_BOARD},
                "top": {"type": "integer", "minimum": 1, "maximum": 40, "default": 10,
                        "description": "返回热度最高的前 N 个分类"},
            },
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "board": {"type": "string"}, "count": {"type": "integer"},
                "rows": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["rows"],
        },
    },
]

HANDLERS = {
    "rank_list": tool_rank_list,
    "list_categories": tool_list_categories,
    "scan_categories": tool_scan,
}


# ---------------------------------------------------------------- JSON-RPC

def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def ok(mid, result):
    send({"jsonrpc": "2.0", "id": mid, "result": result})


def err(mid, code, message, data=None):
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    send({"jsonrpc": "2.0", "id": mid, "error": e})


def handle(req):
    method = req.get("method")
    mid = req.get("id")
    params = req.get("params") or {}
    is_notification = "id" not in req

    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        ok(mid, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION,
                           "title": "番茄小说榜单选材（fanqie-rank-scout）"},
            "instructions": ("查询番茄小说的公开榜单：某个分类现在谁在榜上、多少人在读、字数多少。"
                             "先用 list_categories 取分类名，再用 rank_list 看明细，"
                             "用 scan_categories 找还有流量的分类。全部匿名公开页面，不需要登录。"),
        })
        return

    if is_notification:  # notifications/initialized 等，不回包
        return

    if method == "ping":
        ok(mid, {})
        return
    if method == "tools/list":
        ok(mid, {"tools": TOOLS})
        return
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        fn = HANDLERS.get(name)
        if not fn:
            err(mid, -32602, "未知工具: %s" % name)
            return
        try:
            text, structured = fn(args)
        except Exception as exc:  # 工具执行错误按 MCP 约定放 result.isError
            ok(mid, {"content": [{"type": "text", "text": "查询失败：%s" % exc}], "isError": True})
            return
        ok(mid, {"content": [{"type": "text", "text": text}],
                 "structuredContent": structured, "isError": False})
        return
    if method in ("resources/list", "prompts/list", "resources/templates/list"):
        key = {"resources/list": "resources", "prompts/list": "prompts",
               "resources/templates/list": "resourceTemplates"}[method]
        ok(mid, {key: []})
        return
    if method == "logging/setLevel":
        ok(mid, {})
        return

    err(mid, -32601, "不支持的方法: %s" % method)


def main():
    log("started, %d tools, stdio" % len(TOOLS))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            err(None, -32700, "JSON 解析失败: %s" % exc)
            continue
        if isinstance(req, list):  # 批量请求
            for one in req:
                handle(one)
        else:
            handle(req)
    log("stdin closed, exit")


if __name__ == "__main__":
    main()
