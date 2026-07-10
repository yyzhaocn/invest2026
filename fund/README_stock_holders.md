# 股票股东查询功能

## 功能说明

`stockHolders()` 方法用于查询指定股票的股东持股明细信息，包括股东名称、持股数量、持股比例、持股市值等。

## 使用方法

### 基本用法

```python
from fund_analyzer import FundAnalyzer

analyzer = FundAnalyzer()

# 查询股票股东信息（使用默认报告日期）
result = analyzer.stockHolders("300124")

# 指定报告日期
result = analyzer.stockHolders("300124", report_date="2025-09-30")

# 分页查询
result = analyzer.stockHolders("300124", report_date="2025-09-30", page_num=1, page_size=50)
```

### 参数说明

- `stockcode` (str): 股票代码，如 '300124', '002460' 等
- `report_date` (str, 可选): 报告日期，格式 'YYYY-MM-DD'，默认为最新季度末
- `page_num` (int, 可选): 页码，默认1
- `page_size` (int, 可选): 每页数量，默认30

### 返回值

返回一个字典，包含以下字段：

```python
{
    'stockcode': '300124',           # 股票代码
    'report_date': '2025-09-30',    # 报告日期
    'holders': [                     # 股东列表
        {
            'stockcode': '300124',          # 股票代码（已添加）
            'report_date': '2025-09-30',   # 报告日期（已添加）
            'update_time': '2025-01-04 10:30:00',  # 更新时间（已添加）
            'holder_code': '...',           # 股东代码
            'holder_name': '...',           # 股东名称
            'hold_amount': 1234567,         # 持股数量
            'hold_ratio': 5.23,            # 持股比例（%）
            'hold_value': 12345678,        # 持股市值
            'change_amount': 12345,        # 持股变化数量
            'change_ratio': 0.12,          # 持股比例变化（%）
            'holder_type': '...',          # 股东类型代码
            'holder_type_name': '...'      # 股东类型名称
        },
        ...
    ],
    'total': 100,                    # 总记录数
    'page_num': 1,                   # 当前页码
    'page_size': 30                  # 每页数量
}
```

## CSV文件保存

### 自动保存

每次调用 `stockHolders()` 方法时，数据会自动保存到CSV文件：
- **文件路径**: `../generated/em/stockHolders.csv`
- **编码格式**: UTF-8 with BOM (utf-8-sig)，便于Excel打开
- **更新策略**: 如果同一股票代码和报告日期的数据已存在，会先删除旧数据再添加新数据

### CSV文件字段

CSV文件包含以下字段：
- `stockcode`: 股票代码
- `report_date`: 报告日期
- `update_time`: 更新时间（格式：YYYY-MM-DD HH:MM:SS）
- `holder_code`: 股东代码
- `holder_name`: 股东名称
- `hold_amount`: 持股数量
- `hold_ratio`: 持股比例（%）
- `hold_value`: 持股市值
- `change_amount`: 持股变化数量
- `change_ratio`: 持股比例变化（%）
- `holder_type`: 股东类型代码
- `holder_type_name`: 股东类型名称

### 数据排序

CSV文件中的数据按以下顺序排序：
1. 股票代码（升序）
2. 报告日期（降序，最新的在前）
3. 持股比例（降序，持股最多的在前）

## 使用示例

### 示例1：查询最新季度股东信息

```python
from fund_analyzer import FundAnalyzer

analyzer = FundAnalyzer()
result = analyzer.stockHolders("300124")

if result:
    print(f"股票 {result['stockcode']} 的股东信息（{result['report_date']}）")
    print(f"共 {result['total']} 个股东")
    
    for i, holder in enumerate(result['holders'][:10], 1):
        print(f"{i}. {holder['holder_name']}: {holder['hold_ratio']:.2f}%")
```

### 示例2：查询指定日期股东信息

```python
# 查询2025年第三季度末的股东信息
result = analyzer.stockHolders("300124", report_date="2025-09-30")

if result:
    print(f"\n前10大股东:")
    for i, holder in enumerate(result['holders'][:10], 1):
        print(f"{i:2d}. {holder['holder_name']:20s} "
              f"{holder['hold_ratio']:6.2f}% "
              f"{holder['hold_amount']:>15,.0f}股")
```

### 示例3：分页查询所有股东

```python
def get_all_holders(analyzer, stockcode, report_date=None):
    """获取所有股东信息（分页）"""
    all_holders = []
    page_num = 1
    page_size = 30
    
    while True:
        result = analyzer.stockHolders(
            stockcode, 
            report_date=report_date,
            page_num=page_num,
            page_size=page_size
        )
        
        if not result or not result['holders']:
            break
        
        all_holders.extend(result['holders'])
        
        # 检查是否还有更多数据
        if len(result['holders']) < page_size:
            break
        
        page_num += 1
    
    return all_holders

# 使用
analyzer = FundAnalyzer()
all_holders = get_all_holders(analyzer, "300124", "2025-09-30")
print(f"共获取 {len(all_holders)} 个股东信息")
```

## 报告日期说明

如果不指定 `report_date`，方法会自动使用最新季度末日期：
- Q1: 3月31日
- Q2: 6月30日
- Q3: 9月30日
- Q4: 12月31日

## 数据字段说明

- **holder_code**: 股东代码（机构代码或个人ID）
- **holder_name**: 股东名称
- **hold_amount**: 持股数量（股）
- **hold_ratio**: 持股比例（%）
- **hold_value**: 持股市值（元）
- **change_amount**: 持股变化数量（股），正数表示增持，负数表示减持
- **change_ratio**: 持股比例变化（%）
- **holder_type**: 股东类型代码
- **holder_type_name**: 股东类型名称（如：机构、个人、基金等）

## CSV文件保存

### 自动保存

每次调用 `stockHolders()` 方法时，数据会自动保存到CSV文件：
- **文件路径**: `../generated/em/stockHolders.csv`
- **编码格式**: UTF-8 with BOM (utf-8-sig)，便于Excel打开
- **更新策略**: 如果同一股票代码和报告日期的数据已存在，会先删除旧数据再添加新数据

### CSV文件字段

CSV文件包含以下字段：
- `stockcode`: 股票代码
- `report_date`: 报告日期
- `update_time`: 更新时间（格式：YYYY-MM-DD HH:MM:SS）
- `holder_code`: 股东代码
- `holder_name`: 股东名称
- `hold_amount`: 持股数量
- `hold_ratio`: 持股比例（%）
- `hold_value`: 持股市值
- `change_amount`: 持股变化数量
- `change_ratio`: 持股比例变化（%）
- `holder_type`: 股东类型代码
- `holder_type_name`: 股东类型名称

### 数据排序

CSV文件中的数据按以下顺序排序：
1. 股票代码（升序）
2. 报告日期（降序，最新的在前）
3. 持股比例（降序，持股最多的在前）

### 查看CSV文件

```python
import pandas as pd

# 读取CSV文件
df = pd.read_csv('../generated/em/stockHolders.csv')

# 查看特定股票的股东信息
df_stock = df[df['stockcode'] == '300124']
print(df_stock)

# 查看最新更新的数据
df_latest = df.sort_values('update_time', ascending=False).head(10)
print(df_latest)
```

## 注意事项

1. **API限制**: 注意不要过于频繁地请求API
2. **数据格式**: API返回的数据格式可能因时间而变化，代码已处理多种格式
3. **分页**: 如果股东数量较多，需要使用分页查询
4. **错误处理**: 方法会捕获异常并返回None，建议检查返回值
5. **CSV文件**: 数据会自动保存到CSV文件，每次查询会更新相同股票代码和报告日期的数据
6. **更新时间**: 每次查询都会添加 `update_time` 字段，记录数据获取时间

## 测试

运行测试脚本：

```bash
python fund/test_stock_holders.py
```

## API参考

该方法调用东方财富的股东持股明细API：
- URL: `https://data.eastmoney.com/dataapi/zlsj/detail`
- 方法: GET
- 参数: 见方法实现

