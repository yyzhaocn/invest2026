# HAR文件处理工作流 - 完整文档

## 📋 目录

- [概述](#概述)
- [快速开始](#快速开始)
- [工作流组件](#工作流组件)
- [详细文档](#详细文档)
- [使用示例](#使用示例)
- [常见问题](#常见问题)
- [技术支持](#技术支持)

## 🎯 概述

这是一个完整的HAR文件处理工作流，专门用于从Chrome DevTools的HAR文件中提取和分析网络请求数据，特别是东方财富股票相关的API调用。通过一系列工具，可以批量获取URL响应数据，分析API模式，并生成详细报告。

### 主要功能

- ✅ **HAR文件解析**: 从Chrome DevTools导出的HAR文件中提取网络请求数据
- ✅ **批量URL处理**: 并发处理大量URL，获取实时响应数据
- ✅ **API数据分析**: 分析API响应结构，分类统计，生成详细报告
- ✅ **盘口异动数据**: 获取东方财富股票盘口异动数据
- ✅ **Chrome事件分析**: 分析Chrome DevTools的Network、Console、Performance数据
- ✅ **数据可视化**: 生成响应时间分布、成功率统计等图表
- ✅ **多种输出格式**: 支持JSON、CSV、Excel等多种输出格式

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install requests pandas matplotlib seaborn

# 克隆或下载项目文件
cd stock/
```

### 2. 基本使用流程

```bash
# 步骤1: 解析HAR文件，生成URL列表
python harParser.py quote_stock.har

# 步骤2: 批量处理URL列表
python batch_url_processor.py quote_stock.urls

# 步骤3: 分析API数据
python api_data_analyzer.py batch_url_results.json

# 步骤4: 查看结果
ls -la *.json *.csv
```

### 3. 获取盘口异动数据

```bash
# 获取今天的盘口异动数据
python pkyd_example.py

# 测试不同参数
python test_pkyd_by_day.py
```

## 🔧 工作流组件

### 核心工具

| 工具 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `harParser.py` | HAR文件解析 | HAR文件 | URL列表/内容文件 |
| `crawhar.py` | 高级URL爬取 | URL列表文件 | JSON/摘要文件 |
| `batch_url_processor.py` | 批量URL处理 | URL列表文件 | JSON/CSV结果 |
| `api_data_analyzer.py` | API数据分析 | 批量处理结果 | 详细分析报告 |
| `har_url_extractor.py` | HAR文件提取 | HAR文件 | URL响应数据 |
| `live_url_fetcher.py` | 实时URL获取 | 目标URL列表 | 实时响应数据 |
| `pkyd_example.py` | 盘口异动数据 | 日期参数 | CSV文件 |

### 辅助工具

| 工具 | 功能 | 用途 |
|------|------|------|
| `chrome_event_extractor.py` | Chrome事件提取 | 分析网络事件模式 |
| `chrome_network_extractor.py` | 网络数据提取 | 专门处理Network标签页 |
| `chrome_devtools_analyzer.py` | DevTools综合分析 | 分析Network/Console/Performance |
| `test_pkyd_by_day.py` | 功能测试 | 测试盘口异动数据获取 |

## 📚 详细文档

### 1. [HAR工作流文档](README_HAR_Workflow.md)
- 完整的工作流说明
- 各组件使用方法
- 配置选项和参数
- 性能优化建议

### 2. [输出文件说明](README_Output_Files.md)
- JSON文件格式说明
- CSV文件结构说明
- 数据访问示例
- 数据可视化方法

### 3. [Python脚本说明](README_Python_Scripts.md)
- 各脚本功能详解
- 使用方法和参数
- 错误处理机制
- 扩展开发指南

### 4. [harParser.py工具说明](README_harParser.md)
- HAR文件解析工具详解
- 与其他工具的关系
- API接口识别逻辑
- 内容抓取功能

### 5. [crawhar.py工具说明](README_crawhar.md)
- 高级URL爬取工具详解
- 双引擎爬取系统
- 功能重叠分析和改进建议
- 性能对比和推荐使用场景

## 💡 使用示例

### 示例1: 批量处理URL

```python
from batch_url_processor import BatchUrlProcessor

# 初始化处理器
processor = BatchUrlProcessor(max_workers=3)

# 加载URL列表
urls = processor.load_urls_from_file('/tmp/quote_stock.urls')

# 批量处理
results = processor.process_urls_batch(urls, delay=0.3)

# 生成报告
report = processor.generate_summary_report(results)
print(report)

# 保存结果
processor.save_results_to_json(results, 'batch_url_results.json')
processor.save_results_to_csv(results, 'batch_url_results.csv')
```

### 示例2: 分析API数据

```python
from api_data_analyzer import APIDataAnalyzer

# 初始化分析器
analyzer = APIDataAnalyzer('batch_url_results.json')
analyzer.load_results()

# 生成摘要报告
summary = analyzer.generate_api_summary()
print(summary)

# 分析不同类别
categories = analyzer.analyze_api_categories()
for category_name, api_list in categories.items():
    if api_list:
        analyzer.display_api_data(category_name, api_list)
```

### 示例3: 解析HAR文件

```bash
# 基本解析，生成URL列表
python harParser.py quote_stock.har

# 详细模式，显示接口信息
python harParser.py quote_stock.har -v

# 抓取内容模式，下载所有URL内容
python harParser.py quote_stock.har --fetch

# 抓取内容但不包含URL列
python harParser.py quote_stock.har --fetch --no-url
```

### 示例4: 高级URL爬取

```bash
# 基本爬取
python crawhar.py quote_stock.urls

# 指定延迟和详细输出
python crawhar.py quote_stock.urls --delay 1.0 --verbose

# 显示结果预览
python crawhar.py quote_stock.urls --preview

# 交互式查看爬取结果
python crawhar.py quote_stock.urls
# 然后输入序号查看详细JSON数据
```

### 示例5: 获取盘口异动数据

```python
from proto_pkyd import get_pkyd_by_day

# 获取指定日期的数据
result_file = get_pkyd_by_day('2025-08-01', limit=5000)
print(f"数据已保存到: {result_file}")

# 使用自定义文件名
result_file = get_pkyd_by_day_with_custom_filename(
    '2025-08-01', 
    limit=5000,
    filename_format='pkyd_{date}_{timestamp}.csv'
)
```

## 📊 输出文件说明

### 主要输出文件

| 文件名 | 类型 | 内容 | 用途 |
|--------|------|------|------|
| `batch_url_results.json` | JSON | 批量URL处理结果 | 主要数据文件 |
| `batch_url_results.csv` | CSV | 批量处理结果表格 | 数据分析 |
| `api_detailed_analysis.json` | JSON | API详细分析报告 | 分析结果 |
| `pkyd_YYMMDDHHMM.csv` | CSV | 盘口异动数据 | 股票数据 |

### 数据格式示例

```json
{
  "fetch_time": "2025-08-03T06:49:00.106231",
  "total_urls": 19,
  "results": {
    "1": {
      "number": "1",
      "url": "https://push2.eastmoney.com/api/qt/stock/get?...",
      "status_code": 200,
      "response_time": 180.94,
      "success": true,
      "content": {
        "raw": "jQuery...({...})",
        "json": {...},
        "type": "jsonp",
        "parsed": true
      }
    }
  }
}
```

## 🔍 API分类说明

### 股票数据API
- **stock_data**: 股票基本信息
- **index**: 指数行情数据
- **kline**: K线图表数据

### 市场信息API
- **bulletin**: 公告信息
- **news**: 新闻资讯
- **vote**: 投票数据

### 其他API
- **other**: 其他类型API

## ⚙️ 配置选项

### 环境变量

```bash
# 设置默认超时时间
export REQUEST_TIMEOUT=15

# 设置并发数
export MAX_WORKERS=5

# 设置请求延迟
export REQUEST_DELAY=0.5
```

### 配置文件

创建 `config.json`:
```json
{
  "request_timeout": 10,
  "max_workers": 3,
  "request_delay": 0.3,
  "max_retries": 3,
  "output_dir": "./output",
  "log_level": "INFO"
}
```

## 🐛 常见问题

### Q1: 网络请求超时怎么办？
**A**: 增加timeout值或减少并发数
```python
processor = BatchUrlProcessor(max_workers=2)  # 减少并发数
```

### Q2: 内存不足怎么办？
**A**: 分批处理或减少并发数
```python
# 分批处理
for chunk in chunks:
    results = processor.process_urls_batch(chunk)
```

### Q3: 解析失败怎么办？
**A**: 检查响应格式或添加错误处理
```python
try:
    json_data = json.loads(content)
except json.JSONDecodeError:
    print("JSON解析失败，尝试其他格式")
```

### Q4: 文件权限错误怎么办？
**A**: 检查文件路径和权限设置
```bash
# 检查文件权限
ls -la *.json *.csv

# 修改权限
chmod 644 *.json *.csv
```

## 📈 性能优化

### 1. 并发优化
- 根据网络条件调整`max_workers`
- 避免过多并发导致服务器限制

### 2. 内存优化
- 分批处理大量URL
- 及时释放不需要的数据

### 3. 存储优化
- 压缩大型JSON文件
- 定期清理临时文件

## 🔧 技术支持

### 系统要求
- **Python版本**: 3.7+
- **主要依赖**: requests, pandas, json
- **操作系统**: Windows, macOS, Linux

### 依赖安装
```bash
pip install requests pandas matplotlib seaborn
```

### 日志配置
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('har_workflow.log'),
        logging.StreamHandler()
    ]
)
```

### 调试模式
```python
# 启用详细日志
logging.basicConfig(level=logging.DEBUG)

# 打印请求详情
print(f"请求URL: {url}")
print(f"响应状态: {response.status_code}")
```

## 📝 更新日志

### v1.0.0 (2025-08-03)
- ✅ 初始版本发布
- ✅ 支持HAR文件提取
- ✅ 支持批量URL处理
- ✅ 支持API数据分析
- ✅ 支持盘口异动数据获取
- ✅ 支持Chrome DevTools分析
- ✅ 支持多种输出格式
- ✅ 完整的错误处理机制
- ✅ 详细的文档说明

## 🤝 贡献指南

1. **报告问题**: 在GitHub Issues中报告bug或提出建议
2. **提交代码**: Fork项目并提交Pull Request
3. **改进文档**: 帮助改进文档和示例
4. **分享经验**: 分享使用经验和最佳实践

## 📄 许可证

本项目采用MIT许可证，详见LICENSE文件。

---

**注意**: 使用本工具时请遵守相关网站的使用条款和robots.txt规定，合理控制请求频率，避免对服务器造成过大负担。 