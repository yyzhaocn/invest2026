# 🚀 股票分析Web应用 - 快速开始

## 一分钟启动

```bash
cd /Users/yyzhao/pydev/atime/stock
./start_stock_app.sh
```

然后访问：**http://127.0.0.1:5000**

## 📋 使用步骤

### 1️⃣ 启动应用

```bash
# 方法1：使用启动脚本（推荐）
./start_stock_app.sh

# 方法2：直接运行
python app.py
```

### 2️⃣ 分析股票

**选项A：通过首页输入**
1. 打开 http://127.0.0.1:5000
2. 输入股票代码（如：002916）
3. 点击"开始分析"

**选项B：点击热门股票**
- 首页有预设的热门股票，点击即可分析

**选项C：直接访问URL**
```
http://127.0.0.1:5000/analysis/002916
http://127.0.0.1:5000/analysis/600000
http://127.0.0.1:5000/analysis/000001
```

### 3️⃣ 浏览7大分析模块

点击顶部标签切换：
- 📊 **综合评价** - 评分、预测、排名
- 💼 **主力控盘** - 机构参与度分析
- 📰 **舆情监控** - 新闻、公告、研报
- 🔥 **市场热度** - 关注度、参与意愿
- 📈 **趋势研判** - K线、技术指标
- 💰 **资金动向** - 资金流向分析
- 📑 **财务评估** - 财务指标评估

## 🎯 测试用例

### 深南电路（002916）
```
http://127.0.0.1:5000/analysis/002916
```

### 浦发银行（600000）
```
http://127.0.0.1:5000/analysis/600000
```

### 贵州茅台（600519）
```
http://127.0.0.1:5000/analysis/600519
```

### 宁德时代（300750）
```
http://127.0.0.1:5000/analysis/300750
```

## 🛠️ 故障排除

### 问题1：端口被占用
```bash
# 查看占用5000端口的进程
lsof -i :5000

# 杀死进程
kill -9 <PID>

# 或修改app.py中的端口号
```

### 问题2：Flask未安装
```bash
pip install Flask Flask-CORS
```

### 问题3：模块导入错误
```bash
# 安装所有依赖
pip install -r requirements_stock_app.txt
```

### 问题4：页面无法加载
- 检查浏览器控制台错误
- 确认所有HTML文件在templates目录
- 检查app.py是否正常运行

## 📱 快捷键

- **←/→ 方向键**：切换分析模块
- **Ctrl+C**：停止服务器

## 🎨 自定义

### 添加更多热门股票

编辑 `templates/index.html`：
```html
<div class="stock-chip" data-code="YOUR_CODE">YOUR_CODE 股票名称</div>
```

### 修改主题颜色

编辑各个HTML文件的CSS部分

### 集成真实数据

编辑 `app.py` 的API路由函数

## 📊 项目文件

```
stock/
├── app.py                          ← Flask主程序
├── start_stock_app.sh             ← 启动脚本
├── requirements_stock_app.txt     ← 依赖列表
├── README_stock_app.md            ← 详细文档
├── QUICKSTART.md                  ← 本文件
└── templates/                     ← HTML模板
    ├── index.html                 ← 首页
    ├── dashboard.html             ← 仪表盘
    └── [7个模块HTML文件]
```

## ✅ 功能清单

- ✅ 支持任意股票代码输入
- ✅ 7大分析模块
- ✅ 交互式图表（ECharts）
- ✅ 响应式设计
- ✅ 键盘快捷键
- ✅ 标签式导航
- ✅ 实时数据API（框架）
- ✅ 优雅的加载动画

## 🔜 下一步

1. **集成真实数据源**
   - 连接东方财富API
   - 获取实时行情数据

2. **添加用户功能**
   - 用户登录
   - 自选股管理

3. **性能优化**
   - 添加Redis缓存
   - 数据预加载

4. **部署到生产**
   - 使用Gunicorn
   - 配置Nginx

## 📞 需要帮助？

- 查看 `README_stock_app.md` 详细文档
- 检查浏览器控制台错误
- 查看终端输出日志

---

**祝您使用愉快！** 📈✨

