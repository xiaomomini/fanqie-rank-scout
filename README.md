# 番茄小说榜单选材工具（fanqie-rank-scout）

写之前先看榜。这个工具匿名抓取番茄小说公开榜单，把「谁在榜上、多少人在读、多少字、读者密度多少」拉成一张表，
用来判断一个分类还值不值得写、某个题材的读者还剩多少。

**关键词**：番茄小说 · 番茄榜单 · 榜单数据 · 扫榜 · 选材 · 网文数据 · 网文选题 · 在读人数 · 题材热度 · 分类热度 ·
新书榜 · 阅读榜 · 男频 · 女频 · 都市脑洞 · 悬疑脑洞 · 都市高武 · 网文写作 · AI 网文 · 爬虫 · Python · 零依赖 ·
MCP · MCP Server · Model Context Protocol · Claude · Cursor · Cline ·
fanqie · fanqienovel · webnovel · rank tracker · webnovel data

**不用登录、不用 Cookie、不用 Playwright、不用任何第三方库，只要 Python 3.8+。**

## 先看网页版：每日榜单数据

不想装东西？直接看 **[番茄小说榜单数据 · 每日更新](https://xiaomomini.github.io/fanqie-rank-scout/)** ——
四大榜单 TOP10 + 74 个分类的在读中位数，含「在读/万字」读者密度，每天刷新一版快照。
机器可读：`https://xiaomomini.github.io/fanqie-rank-scout/data/latest.json`。

[![榜单数据页预览](https://xiaomomini.github.io/fanqie-rank-scout/preview.png)](https://xiaomomini.github.io/fanqie-rank-scout/)

```bash
python3 fanqie_rank_scout.py                     # 男频新书榜 · 都市脑洞
python3 fanqie_rank_scout.py -b male-read -c 悬疑脑洞
python3 fanqie_rank_scout.py -b male-new --scan  # 扫全部分类，按热度排序
python3 fanqie_rank_scout.py -c 都市脑洞 --csv 都市脑洞.csv
```

## 当 MCP Server 用（Claude Desktop / Cursor / Cline / Continue）

同一份代码也是 MCP Server，模型可以自己调榜单，不用你手敲命令。

```bash
uvx --from git+https://github.com/xiaomomini/fanqie-rank-scout fanqie-rank-mcp
```

写进客户端配置（Claude Desktop 的 `claude_desktop_config.json`、Cursor 的 `mcp.json`、Cline 的 MCP Servers）：

```json
{
  "mcpServers": {
    "fanqie-rank": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/xiaomomini/fanqie-rank-scout", "fanqie-rank-mcp"]
    }
  }
}
```

不想装 uv 就直接指向脚本（绝对路径）：

```json
{"mcpServers": {"fanqie-rank": {"command": "python3", "args": ["/绝对路径/fanqie_rank_mcp.py"]}}}
```

三个工具：

| 工具 | 参数 | 作用 |
|---|---|---|
| `rank_list` | `board`, `category`, `limit`, `resolve` | 某分类前 10 名：书名/作者/在读/字数/在读密度 |
| `list_categories` | `board` | 该板块全部可查分类（男频新书榜 19 个、女频 18 个） |
| `scan_categories` | `board`, `top` | 扫全部分类，按前 10 在读中位数排序，找还有流量的分类 |

装好后直接问：「番茄男频新书榜都市脑洞现在谁在榜上」「扫一下女频新书榜，哪个分类还有读者」。

实测（官方 `mcp` Python SDK 客户端，`initialize` → `tools/list` → `tools/call` 全过，协议 2025-06-18）：

```
榜单：女频新书榜 · 古言脑洞（前 3，共 3 条）
| 排名 | 书名 | 作者 | 在读 | 字数(万) | 在读/万字 | 状态 |
| 1 | 始皇陛下，太子扶苏他又在演！ | 思不诗 | 17万 | 19.8 | 0.86 | 连载中 |
| 2 | 听真千金心声，皇城权贵瑟瑟发抖 | 凤点江山 | 16.4万 | 28.8 | 0.57 | 已完结 |
| 3 | 我，曹操之女，被金榜曝光了 | 冰镇蜜瓜 | 14.8万 | 18.2 | 0.81 | 连载中 |
```


## 真实输出（2026-11-24 抓取，男频新书榜 · 都市脑洞）

```
榜单：男频新书榜 · 都市脑洞（数据为页面当前值，平台每天 15:00 前更新）
排名 书名                             作者               在读     字数(万) 在读/字数 状态
1    我的防御好像没有上限             传说中的葡萄       60.5万   24.3     2.49      连载中
2    恋综摆烂，却被京圈大小姐赖上了   辉皇皇             54.5万   21.0     2.60      连载中
3    中奖一个亿，回县城躺平香艳人生   会飞的猪zz         31.8万   21.5     1.48      连载中
4    开局十选九，我成全球刀枪炮了     霸主ou             31.6万   19.4     1.63      连载中
5    我的植物人老婆醒后，咋成病娇了   三桂今天只想摆烂   30万     26.4     1.14      连载中
6    28岁白衬衫开局                   骑着青牛漫步       19.1万   22.9     0.83      连载中
7    穿越红果反派，从整治不烧心开始   系统是假的         17.2万   28.3     0.61      连载中
8    救命！谁家景区npc全是大妖啊      杳杳青云           17.1万   28.6     0.60      连载中
9    什么叫这个混的入是省状元         一颗小猫           14.9万   22.7     0.66      连载中
10   跑男：我，全球顶流，首秀杀疯！   小哎ii             16.9万   13.3     1.27      连载中
```

## 分类热度（`--scan`，男频新书榜前 5）

```
分类           在读中位     TOP1 书名                  TOP1 在读    前10在读合计
都市脑洞        24.6万      我的防御好像没有上限        60.5万       293.6万
动漫衍生        23.3万      火影：第七班拜错师，全忍…   42.9万       278.4万
都市高武        19.2万      全民领主：抽到人族，但来…   45.3万       213.3万
历史脑洞        14.8万      改变历史就变强：开局对掏…   21.7万       152.2万
玄幻脑洞        14.8万      穿书女频：什么叫做言情修…   23.4万       164.9万
```

## 输出列

| 列 | 含义 |
|---|---|
| 排名 | 榜单页原始名次 |
| 书名 / 作者 | 从书籍详情页反查（榜单页有字体混淆，见下） |
| 在读 | 平台展示值，如 `60.5万` |
| 字数(万) | 详情页字数，单位万字 |
| 在读/字数 | 在读(万) ÷ 字数(万)。**同分类横向比较用这个**：>1 说明这本书的读者密度高于榜单中位 |
| 状态 | 连载中 / 已完结 |

`--csv` 另存 CSV（UTF-8 BOM，Excel 直接打开）；`--json` 输出结构化数据。

## 参数

```
-b/--board      male-read / male-new / female-read / female-new（默认 male-new）
-c/--category   分类名，如 都市脑洞（用 --list 查全部）
-n/--limit      输出条数（榜单页只展示前 10）
-r/--rank-id    直接指定榜单路径，如 1_1_262
--scan          扫该板块全部分类，按前 10 在读中位数排序
--no-resolve    不访问书籍详情页（更快，书名/作者会有 □）
--csv / --json  导出
--list          列出所有榜单与分类
```

## 两个实现细节（踩过的坑）

1. **榜单页有字体混淆。** 书名/简介里的部分汉字被替换成 Unicode 私有区字符（`U+E000–U+F8FF`），
   页面用自定义 woff 字体把它们画成正确的字，所以浏览器里看得见、HTML 里是乱码。
   本工具默认从 `/page/<book_id>` 详情页反查真实书名，那个页面是干净文本（也顺带拿到作者和字数）。
   加 `--no-resolve` 可以跳过这 10 次请求，速度更快，但书名会显示成 `□□防御□□□限`。

2. **榜单每天更新，只收 1000 在读以上、已签约未下架的作品。**
   阅读榜要求 30 万字以上，新书榜是 30 万字以下且未断更。页面只渲染前 10 名，`?page=2` 不会翻页。

## 合规

只请求公开页面（`/rank/*`、`/page/*`），每本书一次请求，默认串行/4 线程，不做高频抓取，不涉及任何账号数据。
数据版权归番茄小说所有，本工具仅用于选题分析与学习。

## License

MIT
