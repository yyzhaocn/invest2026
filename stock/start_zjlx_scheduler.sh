#!/bin/bash
# 启动 invest2026 zjlx 定时任务调度器

set -euo pipefail
cd "$(dirname "$0")"

echo "正在启动 zjlx 定时任务调度器 (invest2026/stock)…"

if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

if [ -d "venv" ]; then
    echo "激活虚拟环境 venv…"
    # shellcheck disable=SC1091
    source venv/bin/activate
else
    echo "未发现 venv，使用系统 python3"
fi

python3 -c "import schedule" 2>/dev/null || {
    echo "安装依赖…"
    pip install -r requirements.txt
}

mkdir -p ../generated/em ../generated/cache

echo "启动 scheduler_zjlx.py…"
python3 scheduler_zjlx.py
