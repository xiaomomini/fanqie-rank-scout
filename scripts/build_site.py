#!/usr/bin/env python3
"""生成静态数据站：四大榜单 TOP10 + 分类热度表 -> docs/index.html + docs/data/*.json

数据源与 CLI 同一个（番茄公开榜单，无需登录）。由 GitHub Actions 每天跑一次，
结果提交回仓库，GitHub Pages 直接托管 —— 不依赖任何一台自己的服务器。
"""
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import fanqie_rank_scout as frs  # noqa: E402

OUT = os.path.join(ROOT, "docs")
DATA = os.path.join(OUT, "data")
BOARD_ORDER = ["male-read", "male-new", "female-read", "female-new"]


def fetch_board_top(menu, key, limit=10):
    name = frs.BOARDS[key]
    cats = menu.get(name, {})
    cat = "都市脑洞" if "都市脑洞" in cats else next(iter(cats), None)
    if not cat:
        return None
    path = cats[cat]
    rows = frs.parse_rank(frs.http_get("%s/rank/%s" % (frs.BASE, path)))[:limit]
    for r in rows:
        try:
            info = frs.resolve_book(r["book_id"])
            r["title"] = info.get("title") or r["title"]
            r["author"] = info.get("author") or r["author"]
            r["word_count_wan"] = info.get("word_count_wan")
        except Exception:
            pass
        r["read_num"] = frs.parse_read_count(r["read_text"])
        wc = r.get("word_count_wan")
        r["ratio"] = round(r["read_num"] / 10000.0 / wc, 2) if (r["read_num"] and wc) else None
        if frs.PUA_RE.search(r["title"] or ""):
            r["title"] = frs.PUA_RE.sub("?", r["title"])
        r.pop("url", None)
        r.pop("book_id", None)
    return {"board": name, "category": cat, "rows": rows}


def scan(menu, key):
    name = frs.BOARDS[key]
    cats = menu.get(name, {})
    out = []
    for cat, path in cats.items():
        try:
            items = frs.parse_rank(frs.http_get("%s/rank/%s" % (frs.BASE, path)))
        except Exception as exc:
            sys.stderr.write("skip %s: %s\n" % (cat, exc))
            continue
        if not items:
            continue
        reads = [r for r in (frs.parse_read_count(i["read_text"]) for i in items) if r]
        if not reads:
            continue
        out.append({
            "category": cat,
            "median_read": int(statistics.median(reads)),
            "sum_read": sum(reads),
            "top_read": reads[0],
        })
        time.sleep(0.2)
    out.sort(key=lambda r: r["median_read"], reverse=True)
    return {"board": name, "rows": out}


def load_prev():
    """读上一份快照（除今天外最新的 history 文件），用于算日变化。"""
    hist_dir = os.path.join(DATA, "history")
    if not os.path.isdir(hist_dir):
        return None, {}
    files = sorted(f for f in os.listdir(hist_dir) if f.endswith(".json"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".json"
    prev = [f for f in files if f != today]
    if not prev:
        return None, {}
    path = os.path.join(hist_dir, prev[-1])
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return None, {}
    idx = {}
    for s in d.get("scans", []):
        for r in s.get("rows", []):
            idx[(s["board"], r["category"])] = r.get("median_read")
    return d.get("generated_at", "")[:10], idx


def wan(v):
    if not v:
        return "-"
    return ("%.1f万" % (v / 10000.0)) if v >= 10000 else str(v)


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(data):
    day = data["generated_at"][:10]
    parts = []
    for b in data["boards"]:
        rows = b["rows"]
        trs = []
        for r in rows:
            trs.append(
                "<tr><td class=n>%d</td><td class=t>%s</td><td class=a>%s</td>"
                "<td class=r>%s</td><td class=r>%s</td><td class=r>%s</td></tr>" % (
                    r["rank"], esc(r["title"]), esc(r["author"]),
                    esc(r.get("read_text") or "-"),
                    ("%.1f" % r["word_count_wan"]) if r.get("word_count_wan") else "-",
                    ("%.2f" % r["ratio"]) if r.get("ratio") else "-"))
        parts.append(
            '<section><h2>%s <small>· %s</small></h2><table><thead><tr>'
            "<th>#</th><th>书名</th><th>作者</th><th>在读</th><th>万字</th><th>在读/万字</th>"
            "</tr></thead><tbody>%s</tbody></table></section>" % (
                esc(b["board"]), esc(b["category"]), "".join(trs)))

    heat = []
    for s in data["scans"]:
        trs = []
        for r in s["rows"][:12]:
            d = r.get("delta")
            if d is None:
                dcell = "<td class=r>—</td>"
            elif d == 0:
                dcell = "<td class='r flat'>0</td>"
            else:
                cls = "up" if d > 0 else "down"
                sign = "+" if d > 0 else "−"
                dcell = "<td class='r %s'>%s%s</td>" % (cls, sign, wan(abs(d)))
            trs.append("<tr><td class=t>%s</td><td class=r>%s</td>%s<td class=r>%s</td></tr>" % (
                esc(r["category"]), wan(r["median_read"]), dcell, wan(r["top_read"])))
        heat.append('<div class=card><h3>%s</h3><table><thead><tr><th>分类</th>'
                    "<th>在读中位</th><th>日变化</th><th>榜首在读</th></tr></thead><tbody>%s</tbody></table></div>"
                    % (esc(s["board"]), "".join(trs)))

    prev_day = data.get("prev_day")
    prev_note = ("与 %s 对比" % esc(prev_day)) if prev_day else "首份快照，明日起显示日变化"

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>番茄小说榜单数据 · %(day)s · 每日自动更新</title>
<meta name="description" content="番茄小说四大榜单 TOP10 与各分类在读热度，每天自动更新。看哪个分类还有流量、在读/字数比多少，判断题材还值不值得写。">
<style>
:root{--bg:#0f1115;--fg:#e6e6e6;--dim:#8b949e;--line:#232830;--acc:#4ea1ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:22px;margin:0 0 6px}
.sub{color:var(--dim);font-size:13px;margin-bottom:22px}
h2{font-size:17px;margin:28px 0 10px;border-left:3px solid var(--acc);padding-left:9px}
h2 small{color:var(--dim);font-weight:400;font-size:13px}
h3{font-size:14px;margin:0 0 8px;color:var(--acc)}
table{width:100%%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;color:var(--dim);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px}
td{padding:6px 8px;border-bottom:1px solid #191d24}
td.n{color:var(--dim);width:28px}
td.t{max-width:230px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
td.a{color:var(--dim);max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
td.r{text-align:right;font-variant-numeric:tabular-nums}
.up{color:#3fb950}.down{color:#f85149}.flat{color:var(--dim)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.card{background:#14181f;border:1px solid var(--line);border-radius:8px;padding:14px}
footer{margin-top:36px;color:var(--dim);font-size:12.5px;border-top:1px solid var(--line);padding-top:14px}
a{color:var(--acc)}
</style></head><body><div class=wrap>
<h1>番茄小说榜单数据</h1>
<div class=sub>%(day)s 生成 · 每天自动更新 · 数据取自番茄小说公开榜单页（无需登录），在读为平台口径</div>
%(boards)s
<h2>分类热度 <small>· 前 10 在读中位数，看哪个分类还有流量（%(prevnote)s）</small></h2>
<div class=grid>%(heat)s</div>
<footer>
在读/万字 = 在读人数 ÷ 字数（万），越高说明这个题材用更少的字数拿到更多读者。<br>
数据来源：<a href="https://github.com/xiaomomini/fanqie-rank-scout">xiaomomini/fanqie-rank-scout</a>
（同名 CLI / MCP Server，可本地跑、可让模型调用）。
本页每天刷新一版快照，机器可读数据：<a href="data/latest.json">data/latest.json</a>。
</footer></div></body></html>
""" % {"day": day, "boards": "".join(parts), "heat": "".join(heat), "prevnote": prev_note}
    return html


def main():
    html = frs.http_get("%s/rank/1_2_262" % frs.BASE)
    menu = frs.parse_menu(html)
    if not menu:
        sys.stderr.write("导航解析失败\n")
        return 1
    data = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "https://fanqienovel.com/rank", "boards": [], "scans": []}
    for key in BOARD_ORDER:
        try:
            b = fetch_board_top(menu, key)
            if b:
                data["boards"].append(b)
                print("board %s ok (%d rows)" % (key, len(b["rows"])))
        except Exception as exc:
            sys.stderr.write("board %s failed: %s\n" % (key, exc))
    for key in BOARD_ORDER:
        try:
            data["scans"].append(scan(menu, key))
            print("scan %s ok" % key)
        except Exception as exc:
            sys.stderr.write("scan %s failed: %s\n" % (key, exc))
    if not data["boards"]:
        sys.stderr.write("没有任何榜单数据，放弃写入\n")
        return 1

    prev_day, prev_idx = load_prev()
    if prev_day:
        data["prev_day"] = prev_day
        for s in data["scans"]:
            for r in s["rows"]:
                old = prev_idx.get((s["board"], r["category"]))
                r["delta"] = (r["median_read"] - old) if (old and r["median_read"]) else None
        print("delta vs %s: %d category rows" % (
            prev_day, sum(1 for s in data["scans"] for r in s["rows"] if r.get("delta") is not None)))

    os.makedirs(os.path.join(DATA, "history"), exist_ok=True)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(render(data))
    with open(os.path.join(DATA, "latest.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    hist = os.path.join(DATA, "history", data["generated_at"][:10] + ".json")
    with open(hist, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print("wrote docs/index.html + %s" % hist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
