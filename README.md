# invest2026 — A-share stock & fund research toolkit

Personal investment research workspace: Flask web app for A-share analysis, favorites management, Pi chat, and fund analysis tools.

## Structure

```
invest2026/
├── stock/          # Stock web app (Flask, port 5050)
├── fund/           # Fund analysis scripts & web app (port 5001)
├── market/         # Market skills: fund-list/fund-pl/fund-trend (基金), stock-list/stock-trend (股票)
├── shared/         # Favorites config & pick notes (local, not in git)
├── templates/      # Fund web templates
└── generated/      # Runtime market data (local cache, not in git)
```

## Quick start — Stock web

```bash
cd stock
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_stock_app.txt -r requirements.txt
cp ../shared/favoriteStocks.ini.example ../shared/favoriteStocks.ini
cp ../shared/stockProperties.json.example ../shared/stockProperties.json
./start_stock_app.sh
```

Open **http://127.0.0.1:5050** (macOS AirPlay often occupies 5000; app uses 5050 by default when started manually).

Manual start:

```bash
cd stock && source venv/bin/activate
python -c "from app import app; app.run(debug=True, host='0.0.0.0', port=5050, use_reloader=False)"
```

## Quick start — Fund web

```bash
cd fund
pip install flask requests pandas beautifulsoup4 lxml
python fund_web_app.py
```

Open **http://127.0.0.1:5001**

## Features

- **Stock**: realtime quotes, capital flow, stock comments, favorites groups, sector pick, Pi agent chat, iwencai/xuangu import
- **Fund**: fund parsing, holdings analysis, HTML reports, concept fund screening

## Local config

| Path | Purpose |
|------|---------|
| `shared/favoriteStocks.ini` | Watchlist groups |
| `shared/stockProperties.json` | Per-stock tags/properties |
| `shared/pick_notes/` | Group pick rationale (markdown) |
| `shared/iwencai_cookie.txt` | Iwencai session cookie (optional) |
| `generated/em/YYMMDD/` | Daily East Money CSV snapshots |

Copy `.example` files in `shared/` to bootstrap an empty install.

## Data

Market CSV files under `generated/` are **not** committed. Fetch fresh data using the scripts in `stock/` or the zjlx scheduler after clone:

```bash
cd stock && ./start_zjlx_scheduler.sh
```

## License

Private personal project.
