# 股票数据定时任务调度器

这个脚本用于在交易时间内每2分钟自动执行股票数据获取任务，包括：
1. `getRealtimeQuote` - 获取实时股票行情数据
2. `get_zjlx` - 获取资金流向数据

## 功能特点

- 🕐 **智能时间控制**：只在交易时间内执行（9:25-11:30, 13:00-15:05）
- 📅 **周末排除**：自动跳过周六和周日
- ⏱️ **精确调度**：每2分钟执行一次
- 📝 **详细日志**：记录执行状态和错误信息
- 🚀 **自动启动**：如果当前在交易时间内，启动后立即执行一次
- 🔄 **顺序执行**：先执行getRealtimeQuote，再执行get_zjlx

## 安装依赖

```bash
pip3 install -r requirements.txt
```

## 使用方法

### 方法1：使用启动脚本（推荐）

```bash
cd stock
./start_zjlx_scheduler.sh
```

### 方法2：直接运行Python脚本

```bash
cd stock
python3 scheduler_zjlx.py
```

### 策略选股（可手动或等调度器 17:35 自动跑）

```bash
cd stock
venv/bin/python3 rise_prob_picks.py
venv/bin/python3 strategy_picks.py
```

## 停止程序

按 `Ctrl+C` 停止调度器。

## 日志文件

程序运行时会生成 `zjlx_scheduler.log` 日志文件，记录所有执行信息。

## 输出文件

数据文件会保存在 `generated/em/` 目录下：

- **实时行情数据**：`realtime_quote_YYMMDDHHMM.json`
- **资金流向数据**：`zjlx_YYMMDDHHMM.csv`

## 交易时间

- **上午**：9:25 - 11:30
- **下午**：13:00 - 15:05
- **排除**：周六、周日及法定节假日

## 注意事项

1. 确保网络连接正常
2. 确保有足够的磁盘空间存储数据文件
3. 建议在服务器或稳定的环境中运行
4. 如需长期运行，建议使用 `nohup` 或 `screen` 等工具

## 故障排除

如果遇到问题，请检查：
1. Python环境和依赖包是否正确安装
2. 网络连接是否正常
3. 查看日志文件中的错误信息
4. 确保 `utils_reem.py` 文件中的 `get_zjlx` 函数可用
