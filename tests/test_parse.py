#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小单测：解析逻辑不依赖网络。运行：python3 -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fanqie_rank_scout as scout  # noqa: E402

ITEM = '''<div class="rank-book-item"><div class="book-item-index"><h1>01</h1><p>-</p></div>
<div class="book-item-text">
<div class="title"><a href="/page/7000000000000000001" class="font-X">\u7cfb\u7edf\ue50b\u5bb3</a></div>
<div class="author"><a href="/author-page/1" target="_blank"><span class="font-X">\u8584\u8377\u7cd6</span></a></div>
<div class="desc abstract">...</div>
<div class="book-item-footer"><span class="book-item-footer-status">\u8fde\u8f7d\u4e2d</span>
<span class="book-item-count">\u5728\u8bfb\uff1a<!-- -->57.4\u4e07</span>
<span class="book-item-footer-last"><a class="chapter" href="/reader/1">\u6700\u8fd1\u66f4\u65b0\uff1a<!-- -->\u7b2c141\u7ae0 \u5206\u5934\u884c\u52a8</a></span>
<span class="book-item-footer-time">2026-11-24 23:21</span></div></div></div>'''

MENU = '''<div tabindex="0" aria-expanded="false" class="arco-menu-inline-header">
<span><span>\u7537\u9891\u65b0\u4e66\u699c</span></span></div>
<div class="arco-menu-inline-content"><div class="arco-menu-item"><span><span class="arco-menu-item-inner">
<a level="2" href="/rank/1_1_262">\u90fd\u5e02\u8111\u6d1e</a></span></span></div></div>
<div tabindex="0" aria-expanded="false" class="arco-menu-inline-header">
<span><span>\u5973\u9891\u65b0\u4e66\u699c</span></span></div>
<div class="arco-menu-inline-content"><div class="arco-menu-item"><span><span class="arco-menu-item-inner">
<a level="2" href="/rank/0_1_267">\u73b0\u8a00\u8111\u6d1e</a></span></span></div></div>'''


class TestScout(unittest.TestCase):
    def test_parse_read_count(self):
        self.assertEqual(scout.parse_read_count("57.4\u4e07"), 574000)
        self.assertEqual(scout.parse_read_count("9800"), 9800)
        self.assertIsNone(scout.parse_read_count(""))

    def test_parse_rank(self):
        rows = scout.parse_rank(ITEM)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["rank"], 1)
        self.assertEqual(r["book_id"], "7000000000000000001")
        self.assertEqual(r["read_text"], "57.4\u4e07")
        self.assertEqual(r["status"], "\u8fde\u8f7d\u4e2d")
        self.assertIn("\u7b2c141\u7ae0", r["last_chapter"])
        # 字体混淆字符保留原样，由 clean/resolve 处理
        self.assertRegex(r["title"], scout.PUA_RE)

    def test_parse_menu(self):
        menu = scout.parse_menu(MENU)
        self.assertEqual(menu["\u7537\u9891\u65b0\u4e66\u699c"]["\u90fd\u5e02\u8111\u6d1e"], "1_1_262")
        self.assertEqual(menu["\u5973\u9891\u65b0\u4e66\u699c"]["\u73b0\u8a00\u8111\u6d1e"], "0_1_267")

    def test_pad_truncates(self):
        self.assertEqual(scout.disp_width(scout.pad("\u4e2d\u6587\u4e66\u540d", 4)), 4)
        self.assertTrue(scout.pad("a" * 10, 4).endswith("\u2026"))


if __name__ == "__main__":
    unittest.main()
