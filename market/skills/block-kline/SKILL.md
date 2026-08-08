---
name: block-kline
description: 为指定板块生成 embed HTML，嵌入东财官方 K 线图（含 RSI 副图）与分时快照图，附板块概览与成分涨幅榜。输入板块代码（BKxxxx）或名称。当用户说「某板块做成 embed 页面/嵌入图」「板块K线图嵌入」「webquoteklinepic 图片」「生成板块HTML」时使用。反触发：只看板块走势文字表用 block-trend；板块成分热力图用 stock-hotmap。
---

# block-kline — 板块 embed HTML（东财官方图）

为任意东财板块生成自包含 embed HTML：板块概览 + **东财官方 K 线图（RSI 副图）** + **分时快照图** + 东财页面链接 + 成分涨幅榜。可直接 iframe 嵌入笔记/网页。

## 使用

```bash
python3 /Users/yyz/.agents/skills/stock/block-kline/scripts/block-kline.py <BK代码或名称> [--out 路径] [--top 10] [--json]
```

参数：

- `查询词`：板块代码（`BK0459`）或名称（`元件`/`通信设备`），名称走 boards 列表匹配
- `--out`：输出路径（默认 `cwd/generated/embed_<BK>.html`）
- `--top N`：成分涨幅榜条数（默认 10）
- `--json`：输出 JSON 信息（含 K线/分时图片 URL，便于二次加工）

## 东财官方图片接口

```text
K线(RSI):  https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid=90.BK0459&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={ts}
分时:      https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid=90.BK0459&timespan={ts}
```

- `nid` = `90.BKxxxx`（90 前缀 = 板块指数）
- `timespan` = 当前 epoch 秒（每次生成自动更新，保证图片最新）
- token 为东财 web 版公开常量
- 返回 PNG（K线 520×365 / 分时 578×276），无需鉴权

## embed 页面内容

1. 标题 + 指数/涨跌幅（实时，push2delay stock/get）
2. 指标卡：指数点位 / 成交额 / 成分数
3. 按钮：📈 东财全屏K线图（`#fullScreenChart` 锚点）/ 🔗 板块主页
4. **东财官方 K 线图 + 分时图**（`<img>` 指向官方接口，点击跳板块页）
5. 成分股今日涨幅榜（clist fs=b:BKxxxx，fid=f3 排序）

## 数据源

- 板块概览：`push2delay /api/qt/stock/get?secid=90.BKxxxx`（f43 指数/f170 涨跌/f48 成交额）
- 成分榜：`push2delay clist fs=b:BKxxxx`（fid=f3 今日涨跌幅排序）
- 板块解析：`_shared/boards.py`（名称→BK 代码）

## 注意事项

- 图片接口访问正常（HTTP 200 PNG）；若图片加载失败，检查 timespan 是否过期（重新生成）
- 板块指数 nid 固定为 `90.BKxxxx`；个股页面用 `90.` 换成市场前缀（0/1）即可复用同一接口
- push2his 若被 WAF 风控不影响本技能（概览/成分走 push2delay，图片走 webquotepic 独立域名）
