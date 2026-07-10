# 股票行情API说明文档

## 概述

本文档说明了两个主要的股票行情数据API的区别和用法：

1. **实时行情API** - 获取当前市场实时数据
2. **历史行情API** - 获取指定时间点的历史市场数据

## API对比

### 1. 实时行情API

**URL**: `https://quote.eastmoney.com/stockhotmap/api/getquotedata?quotedata_hash=500ea9710f4d53124555382def877c9070d86909`

**特点**:
- 返回当前时刻的实时股票行情数据
- 包含所有A股股票的当前价格、涨跌幅、成交量等信息
- 数据会实时更新，反映最新市场状态
- 适合实时监控和交易决策

**数据字段**:
- `quotetime`: 行情时间戳
- `data`: 股票数据列表（每只股票包含19个字段）
- `bk`: 板块数据列表
- `hash`: 数据哈希值

**股票数据格式**:
```
"0|平安银行|0|000001|,hsj,sz,hs300,|5|41|8|-128|65|-222|1070|855|822827243.53|34|1231|238883|238887|178"
```
字段说明：
- 序号|股票名称|状态|股票代码|指数|涨跌幅|涨跌幅_1|涨跌幅_2|...|成交额|成交量|换手率|市盈率|市净率

### 2. 历史行情API

**URL**: `https://quote.eastmoney.com/stockhotmap/api/getquotedata_history/日期/时间`

**特点**:
- 返回指定日期的历史行情数据
- 可以获取过去任意时间点的市场快照
- 数据格式与实时API一致
- 适合回测、历史分析和数据挖掘

**参数说明**:
- `日期`: 格式为 `YYYY-MM-DD`，如 `2025-08-14`
- `时间`: 格式为 `HHMM`，如 `1100` 表示11:00
- `period`: 数据周期，默认1000

## 函数实现

### getRealtimeQuote()

获取实时股票行情数据。

```python
def getRealtimeQuote():
    """
    获取实时股票行情数据
    
    返回: 包含实时行情数据的字典
    """
```

**返回值结构**:
```python
{
    'quotetime': 1755141240,
    'hash': 'c3c41aad67cac3f827f8a0a14e578a941a3f0630',
    'stock_data': [
        {
            '序号': '0',
            '股票名称': '平安银行',
            '股票代码': '000001',
            '涨跌幅': 0.05,  # 5%
            '成交额': 822827243.53,
            # ... 其他字段
        }
    ],
    'sector_data': [
        {
            '板块名称': '银行',
            '涨跌幅': 0.90,  # 90%
            '板块代码': 'BK0475'
        }
    ],
    'update_time': '2025-01-13 15:30:00'
}
```

### getHistoryQuote(date_str, time_str='1100', period=1000)

获取历史股票行情数据。

```python
def getHistoryQuote(date_str, time_str='1100', period=1000):
    """
    获取历史股票行情数据
    
    参数:
    date_str: 日期字符串，格式如 '2025-08-14'
    time_str: 时间字符串，格式如 '1100' (11:00)
    period: 数据周期，默认1000
    
    返回: 包含历史行情数据的字典
    """
```

**返回值结构**:
```python
{
    'date': '2025-08-14',
    'time': '1100',
    'period': 1000,
    'quotetime': 1755141240,
    'hash': 'c3c41aad67cac3f827f8a0a14e578a941a3f0630',
    'stock_data': [...],  # 与实时数据格式相同
    'sector_data': [...], # 与实时数据格式相同
    'update_time': '2025-01-13 15:30:00'
}
```

## 使用示例

### 基本用法

```python
from utils_reem import getRealtimeQuote, getHistoryQuote

# 获取实时行情
realtime_data = getRealtimeQuote()
print(f"当前市场有 {len(realtime_data['stock_data'])} 只股票")

# 获取历史行情
history_data = getHistoryQuote('2025-08-14', '1100')
print(f"2025-08-14 11:00 市场有 {len(history_data['stock_data'])} 只股票")
```

### 数据分析示例

```python
# 分析实时市场表现
realtime_data = getRealtimeQuote()

# 统计涨跌分布
up_count = sum(1 for stock in realtime_data['stock_data'] if stock['涨跌幅'] > 0)
down_count = sum(1 for stock in realtime_data['stock_data'] if stock['涨跌幅'] < 0)
flat_count = sum(1 for stock in realtime_data['stock_data'] if stock['涨跌幅'] == 0)

print(f"上涨: {up_count}, 下跌: {down_count}, 平盘: {flat_count}")

# 分析板块表现
sector_performance = {}
for sector in realtime_data['sector_data']:
    sector_performance[sector['板块名称']] = sector['涨跌幅']

# 按涨跌幅排序
sorted_sectors = sorted(sector_performance.items(), key=lambda x: x[1], reverse=True)
print("板块表现排名:")
for i, (sector, change) in enumerate(sorted_sectors[:10]):
    print(f"{i+1}. {sector}: {change:.2%}")
```

### 历史数据对比

```python
# 对比不同时间点的市场表现
morning_data = getHistoryQuote('2025-08-14', '0930')  # 开盘后
noon_data = getHistoryQuote('2025-08-14', '1100')    # 上午收盘前
close_data = getHistoryQuote('2025-08-14', '1500')   # 收盘

# 分析市场情绪变化
def get_market_sentiment(data):
    up_count = sum(1 for stock in data['stock_data'] if stock['涨跌幅'] > 0)
    total_count = len(data['stock_data'])
    return up_count / total_count if total_count > 0 else 0

morning_sentiment = get_market_sentiment(morning_data)
noon_sentiment = get_market_sentiment(noon_data)
close_sentiment = get_market_sentiment(close_data)

print(f"开盘后上涨比例: {morning_sentiment:.2%}")
print(f"上午收盘前上涨比例: {noon_sentiment:.2%}")
print(f"收盘上涨比例: {close_sentiment:.2%}")
```

## 注意事项

1. **API限制**: 请注意API的调用频率限制，避免过于频繁的请求
2. **数据准确性**: 历史数据可能存在延迟或缺失，建议验证数据完整性
3. **错误处理**: 函数已包含基本的错误处理，但仍需注意网络异常情况
4. **数据格式**: 数据以字符串形式返回，需要根据业务需求进行类型转换

## 测试

运行测试脚本验证功能：

```bash
python test_quote_functions.py
```

测试脚本会：
1. 测试实时行情数据获取
2. 测试历史行情数据获取
3. 保存示例数据到JSON文件
4. 显示测试结果汇总

## 更新日志

- 2025-01-13: 初始版本，实现基本的数据获取功能
- 支持实时和历史行情数据获取
- 包含完整的数据解析和错误处理
