#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fanqie-rank-scout — 番茄小说公开榜单选材工具（零依赖）

只抓公开 SSR 页面，不需要登录、不需要 Playwright、不需要 API key。
输出：排名 / 书名 / 作者 / 在读 / 字数(万) / 在读÷字数。

用法示例：
    python3 fanqie_rank_scout.py                          # 男频新书榜 · 都市脑洞
    python3 fanqie_rank_scout.py -b male-read -c 悬疑脑洞
    python3 fanqie_rank_scout.py --list                   # 列出所有榜单与分类
    python3 fanqie_rank_scout.py -c 都市脑洞 --csv out.csv
"""

import argparse
import csv
import gzip
import io
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://fanqienovel.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

BOARDS = {
    "male-read": "男频阅读榜",
    "male-new": "男频新书榜",
    "female-read": "女频阅读榜",
    "female-new": "女频新书榜",
}
DEFAULT_BOARD = "male-new"
DEFAULT_CATEGORY = "都市脑洞"

PUA_RE = re.compile(r"[\ue000-\uf8ff]")


def http_get(url, timeout=20, retries=2):
    """GET 一个公开页面，返回 str。带 gzip 处理与 UA。"""
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("请求失败 %s: %s" % (url, last))


def parse_menu(html):
    """从榜单页导航解出 {板块中文名: {分类名: rank 路径}}。"""
    headers = list(re.finditer(
        r'<div[^>]*class="arco-menu-inline-header"[^>]*>.*?<span><span>([^<]+)</span></span>', html, re.S))
    menu = {}
    for i, m in enumerate(headers):
        name = m.group(1).strip()
        if name not in BOARDS.values():
            continue
        end = headers[i + 1].start() if i + 1 < len(headers) else len(html)
        block = html[m.end():end]
        cats = {}
        for path, cat in re.findall(r'<a level="2" href="/rank/([0-9_]+)">([^<]+)</a>', block):
            cats[cat.strip()] = path
        if cats:
            menu[name] = cats
    return menu


def parse_rank(html):
    """解析榜单页里的 10 个条目（榜单页只展示前 10）。"""
    chunks = re.split(r'<div class="rank-book-item">', html)[1:]
    rows = []
    for ch in chunks[:10]:
        rank = re.search(r'<div class="book-item-index"><h1>(\d+)</h1>', ch)
        book = re.search(r'<div class="title"><a href="/page/(\d+)"', ch)
        if not book:
            continue
        title_raw = re.search(r'<div class="title"><a href="/page/\d+"[^>]*>(.*?)</a>', ch, re.S)
        author_raw = re.search(r'<div class="author"><a [^>]*><span[^>]*>(.*?)</span>', ch, re.S)
        read = re.search(r'book-item-count">在读：<!-- -->([^<]+)</span>', ch)
        status = re.search(r'book-item-footer-status">([^<]+)</span>', ch)
        chapter = re.search(r'最近更新：<!-- -->([^<]+)</a>', ch)
        updated = re.search(r'book-item-footer-time">([^<]+)</span>', ch)
        rows.append({
            "rank": int(rank.group(1)) if rank else len(rows) + 1,
            "book_id": book.group(1),
            "title": clean(title_raw.group(1)) if title_raw else "",
            "author": clean(author_raw.group(1)) if author_raw else "",
            "read_text": read.group(1).strip() if read else "",
            "status": status.group(1).strip() if status else "",
            "last_chapter": clean(chapter.group(1)) if chapter else "",
            "last_update": updated.group(1).strip() if updated else "",
            "url": "%s/page/%s" % (BASE, book.group(1)),
        })
    return rows


def clean(text):
    return re.sub(r"<[^>]+>", "", text).strip()


def parse_read_count(text):
    """'57.4万' -> 574000, '9800' -> 9800, '' -> None"""
    m = re.match(r"([\d.]+)\s*(万)?", text or "")
    if not m:
        return None
    value = float(m.group(1))
    return int(value * 10000) if m.group(2) else int(value)


def resolve_book(book_id):
    """书籍详情页是普通文本（无字体混淆），用来反查真实书名/作者/字数。"""
    html = http_get("%s/page/%s" % (BASE, book_id))
    out = {}
    m = re.search(r"<title>(.*?)(?:完整版在线免费阅读|小说)", html)
    if m:
        out["title"] = clean(m.group(1)).strip("_- ")
    m = re.search(r'"author":\[\{"@type":"Person","name":"([^"]+)"', html)
    if m:
        out["author"] = m.group(1)
    m = re.search(r'<span class="detail">([\d.]+)</span><span class="text">万字</span>', html)
    if m:
        out["word_count_wan"] = float(m.group(1))
    return out


def disp_width(text):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def pad(text, width):
    """按显示宽度补空格；超宽时截断成 …（避免中英混排错位）。"""
    if disp_width(text) > width:
        out = ""
        for ch in text:
            if disp_width(out + ch) > width - 1:
                break
            out += ch
        text = out + "…"
    return text + " " * max(width - disp_width(text), 0)


def print_table(rows, category, board_name):
    headers = ["排名", "书名", "作者", "在读", "字数(万)", "在读/字数", "状态"]
    widths = [4, 32, 18, 8, 8, 9, 6]
    print("榜单：%s · %s（数据为页面当前值，平台每天 15:00 前更新）" % (board_name, category))
    print(" ".join(pad(h, w) for h, w in zip(headers, widths)))
    print("-" * (sum(widths) + len(widths)))
    for r in rows:
        print(" ".join([
            pad(str(r["rank"]), widths[0]),
            pad(r["title"], widths[1]),
            pad(r["author"], widths[2]),
            pad(r["read_text"], widths[3]),
            pad(("%.1f" % r["word_count_wan"]) if r.get("word_count_wan") else "-", widths[4]),
            pad(("%.2f" % r["ratio"]) if r.get("ratio") else "-", widths[5]),
            pad(r["status"], widths[6]),
        ]))


def scan_board(menu, board_name):
    """扫一个板块的全部分类：每类取前 10，输出 TOP1 与在读中位数。"""
    import statistics
    cats = menu.get(board_name, {})
    rows = []
    for name, path in cats.items():
        try:
            page = http_get("%s/rank/%s" % (BASE, path))
        except Exception as exc:
            sys.stderr.write("skip %s: %s\n" % (name, exc))
            continue
        items = parse_rank(page)
        reads = [parse_read_count(i["read_text"]) for i in items]
        reads = [r for r in reads if r]
        if not items:
            continue
        top = items[0]
        try:
            info = resolve_book(top["book_id"])
            top_title = info.get("title") or PUA_RE.sub("□", top["title"])
        except Exception:
            top_title = PUA_RE.sub("□", top["title"])
        rows.append({
            "category": name,
            "path": path,
            "top_title": top_title,
            "top_read": reads[0] if reads else None,
            "median_read": int(statistics.median(reads)) if reads else None,
            "sum_read": sum(reads),
        })
        time.sleep(0.3)
    rows.sort(key=lambda r: r["median_read"] or 0, reverse=True)
    print("板块：%s —— 按前 10 在读中位数排序（分类热度）" % board_name)
    print("%-12s %-8s %-24s %-10s %s" % ("分类", "在读中位", "TOP1 书名", "TOP1 在读", "前10在读合计"))
    print("-" * 78)
    for r in rows:
        print("%-14s %-10s %-26s %-10s %s" % (
            pad(r["category"], 14),
            ("%.1f万" % (r["median_read"] / 10000.0)) if r["median_read"] else "-",
            pad(r["top_title"], 26),
            ("%.1f万" % (r["top_read"] / 10000.0)) if r["top_read"] else "-",
            ("%.1f万" % (r["sum_read"] / 10000.0)) if r["sum_read"] else "-",
        ))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="番茄小说公开榜单选材工具（无需登录）")
    ap.add_argument("-b", "--board", default=DEFAULT_BOARD, choices=sorted(BOARDS),
                    help="榜单：%s（默认 %s）" % ("/".join(sorted(BOARDS)), DEFAULT_BOARD))
    ap.add_argument("-c", "--category", default=DEFAULT_CATEGORY, help="分类名，如 都市脑洞")
    ap.add_argument("-n", "--limit", type=int, default=10, help="输出条数（榜单只列前 10）")
    ap.add_argument("-r", "--rank-id", help="直接指定榜单路径，如 1_1_262（覆盖 -b/-c）")
    ap.add_argument("--no-resolve", action="store_true",
                    help="不访问书籍详情页（更快，但书名/作者可能含乱码字符）")
    ap.add_argument("--csv", help="另存 CSV（UTF-8 BOM，Excel 可直接打开）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--list", action="store_true", help="列出所有榜单分类")
    ap.add_argument("--scan", action="store_true",
                    help="扫该板块全部分类，按前 10 在读中位数排序（找还有流量的分类）")
    args = ap.parse_args(argv)

    # 先抓一页，用来解出导航；用户直接给 rank-id 时也用它确认分类名
    if args.rank_id:
        path = args.rank_id
        html = http_get("%s/rank/%s" % (BASE, path))
        category = args.category
        board_name = BOARDS[args.board]
    else:
        html = http_get("%s/rank/%s" % (BASE, "1_2_262"))  # 任意榜单页都含完整导航
        menu = parse_menu(html)
        board_name = BOARDS[args.board]
        cats = menu.get(board_name, {})
        if args.scan:
            return scan_board(menu, board_name)
        if args.list:
            for key in sorted(BOARDS):
                print(BOARDS[key])
                for name, p in menu.get(BOARDS[key], {}).items():
                    print("  %-8s /rank/%s" % (name, p))
            return 0
        if args.category not in cats:
            sys.stderr.write("找不到分类 %r（-b %s）。可用分类：%s\n"
                             % (args.category, args.board, "、".join(cats)))
            return 2
        path = cats[args.category]
        category = args.category
        if path != "1_2_262":
            html = http_get("%s/rank/%s" % (BASE, path))

    rows = parse_rank(html)[: args.limit]

    if not args.no_resolve:
        def enrich(row):
            try:
                info = resolve_book(row["book_id"])
            except Exception as exc:  # 单本失败不影响整表
                sys.stderr.write("resolve failed %s: %s\n" % (row["book_id"], exc))
                return row
            row["title"] = info.get("title") or row["title"]
            row["author"] = info.get("author") or row["author"]
            row["word_count_wan"] = info.get("word_count_wan")
            return row

        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(enrich, rows))

    for r in rows:
        r["read_num"] = parse_read_count(r["read_text"])
        wc = r.get("word_count_wan")
        # 在读(万) / 字数(万)：与人工扫榜口径一致，如 36.9万在读 / 80万字 = 0.46
        r["ratio"] = round(r["read_num"] / 10000.0 / wc, 2) if (r["read_num"] and wc) else None
        r["category"] = category
        r["board"] = board_name
        # 未 resolve 时把字体混淆字符显示为 □
        if PUA_RE.search(r["title"]):
            r["title"] = PUA_RE.sub("□", r["title"])

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print_table(rows, category, board_name)

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["排名", "书名", "作者", "book_id", "榜单", "分类",
                             "在读", "在读人数", "字数(万)", "在读/字数", "状态",
                             "最近更新", "链接"])
            for r in rows:
                writer.writerow([r["rank"], r["title"], r["author"], r["book_id"],
                                 board_name, category, r["read_text"], r["read_num"],
                                 r.get("word_count_wan"), r.get("ratio"), r["status"],
                                 r["last_update"], r["url"]])
        print("\nCSV 已写入 %s" % args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
