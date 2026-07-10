# 股票分析Web应用

## 📖 简介

这是一个全功能的股票分析Web应用，支持输入任意股票代码进行全方位分析。

## ✨ 功能特性

### 7大分析模块

1. **综合评价** - 股票综合评分、涨跌预测、行业排名
2. **主力控盘** - 机构参与度、主力成本分析
3. **舆情监控** - 新闻、公告、研报追踪
4. **市场热度** - 用户关注度、市场参与意愿
5. **趋势研判** - K线图表、技术指标分析
6. **资金动向** - 资金流向、融资融券数据
7. **财务评估** - 财务比率、盈利能力分析

## 🚀 快速开始

### 1. 安装依赖

```bash
cd /Users/yyzhao/pydev/atime/stock
pip install -r requirements.txt
```

### 2. 启动应用

```bash
python app.py
```

或使用启动脚本：

```bash
chmod +x start_stock_app.sh
./start_stock_app.sh
```

### 3. 访问应用

打开浏览器访问：

```
http://127.0.0.1:5000
```

## 📁 项目结构

```
stock/
├── app.py                          # Flask主应用
├── requirements.txt                # Python依赖
├── start_stock_app.sh             # 启动脚本
├── templates/                      # HTML模板
│   ├── index.html                 # 首页（输入股票代码）
│   ├── dashboard.html             # 分析仪表盘
│   ├── comprehensive_evaluation.html
│   ├── institutional_participation.html
│   ├── sentiment_monitoring.html
│   ├── market_heat.html
│   ├── trend_analysis.html
│   ├── capital_flow.html
│   └── financial_evaluation.html
├── static/                         # 静态资源
│   ├── css/
│   └── js/
└── utils_reem.py                  # 数据获取工具

```

## 🔌 API接口

### 获取股票基本信息
```
GET /api/stock/<stock_code>/info
```

### 获取综合评价数据
```
GET /api/stock/<stock_code>/comprehensive
```

### 获取机构参与数据
```
GET /api/stock/<stock_code>/institutional
```

### 获取舆情数据
```
GET /api/stock/<stock_code>/sentiment
```

### 获取市场热度数据
```
GET /api/stock/<stock_code>/market-heat
```

### 获取资金流向数据
```
GET /api/stock/<stock_code>/capital-flow
```

### 获取财务数据
```
GET /api/stock/<stock_code>/financial
```

## 🎯 使用方法

### 方法1：通过首页输入

1. 访问首页 `http://127.0.0.1:5000`
2. 输入6位股票代码（如：002916）
3. 点击"开始分析"按钮

### 方法2：使用快捷股票

- 点击首页的热门股票标签快速进入分析页面

### 方法3：直接访问URL

```
http://127.0.0.1:5000/analysis/002916
```

## 🛠️ 配置说明

### 修改端口

编辑 `app.py`：

```python
app.run(debug=True, host='0.0.0.0', port=5000)  # 修改port参数
```

### 集成真实数据源

编辑 `app.py` 中的API路由函数，替换mock数据为真实API调用：

```python
from stock.utils_reem import get_stock_comment, get_zjlx_complete

@app.route('/api/stock/<stock_code>/info')
def get_stock_info(stock_code):
    data = get_zjlx_complete(stock_code)
    # 处理数据...
```

## 📊 数据来源

当前版本使用模拟数据。要集成真实数据，需要：

1. 东方财富API - 股票实时行情
2. 资金流向API - 主力资金数据
3. 财务报表API - 公司财务数据
4. 新闻API - 资讯和公告数据

相关工具函数已在 `utils_reem.py` 中实现。

## 🎨 自定义样式

- 修改 `templates/` 中的HTML文件调整布局
- 添加CSS到 `static/css/` 目录
- 添加JavaScript到 `static/js/` 目录

## 🔧 开发调试

启用调试模式：

```python
app.run(debug=True)  # 已默认启用
```

调试模式特性：
- 代码自动重载
- 详细错误信息
- 交互式调试器

## 📝 注意事项

1. **股票代码格式**：必须是6位数字
2. **数据更新**：当前使用模拟数据，需要集成真实API
3. **性能优化**：建议添加缓存机制（Redis）
4. **安全性**：生产环境需要添加认证和限流

## 🚀 生产部署

### 使用Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📈 功能扩展

### 计划功能

- [ ] 用户登录/注册
- [ ] 自选股列表
- [ ] 股票对比功能
- [ ] 预警提醒
- [ ] 数据导出
- [ ] 移动端适配
- [ ] WebSocket实时推送
- [ ] 股票搜索（模糊匹配）

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 📧 联系方式

如有问题，请联系：[your-email@example.com]

---

**Version:** 1.0.0  
**Last Updated:** 2025-10-01

