"""加载 stock 项目根目录下的 `.env`，供 STOCK_CACHE_DIR / FLOW_CHARTS_DIR / KLINE_CACHE_ROOT 等使用。"""
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    _root = Path(__file__).resolve().parent
    load_dotenv(_root / ".env")
