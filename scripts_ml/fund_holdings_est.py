#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基金持仓账户 · 今日估值分析（强制估算口径，用于盘中实时估值）。
"""
import sys, io, json, contextlib, importlib.util, argparse
from pathlib import Path
from datetime import datetime

_STOCK_DIR = Path('/Users/yyz/.agents/skills/stock')
fc_path = _STOCK_DIR / 'fund-pl' / 'scripts' / 'fund-pl.py'
spec = importlib.util.spec_from_file_location('fpl', fc_path)
fpl = importlib.util.module_from_spec(spec)
sys.modules['fpl'] = fpl
sys.path.insert(0, str(Path.cwd()))
spec.loader.exec_module(fpl)
from argparse import Namespace

ACCOUNTS = {
    '基金持仓': {
        '017811': ('东方人工智能主题混合C', 4367),
        '519773': ('交银数据产业灵活配置A', 3574),
        '025209': ('永赢先锋半导体智选C',   6284),
        '022364': ('永赢科技智选混合A',    2686),
        '018125': ('永赢先进制造智选C',    7692),
        '016371': ('信澳业绩驱动混合C',    5921),
        '161631': ('人工智能LOF',          4800),
    },
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--account', default='基金持仓')
    ap.add_argument('--report', default='2026-06-30', help='季报持仓期')
    ap.add_argument('--nav', action='store_true', help='同时显示最新官方净值')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    # 从 portfolio 读实时市值/净值
    account = args.account
    portfolio_sh = _STOCK_DIR / 'portfolio' / 'scripts' / 'portfolio.py'
    pbuf = io.StringIO()
    with contextlib.redirect_stdout(pbuf):
        rc = __import__('subprocess').run(
            [sys.executable, str(portfolio_sh), '--account', account, 'show'],
            capture_output=True, text=True)
    # 简化: 直接用已知持仓（脚本内维护每股最新净值/市值表, 由调用方传入）
    # 这里 fallback 到 fund-pl 直读更新 NAV 后估算。
    from datetime import datetime as _dt
    now = _dt.now()

    # 从直读获取每股最新净值和市值（口径B）供加权
    est_rows = []
    tot_mv = 0.0; tot_est = 0.0
    print(f'=== 账户[{account}] 基金持仓 今日估值估算 ({now.strftime("%m-%d %H:%M")}) ===')
    print(f'口径: 季报({args.report})持仓 × 实时行情 ｜ 仅覆盖股票持仓, 含现金/债券偏差\n')

    # 先拿到每股官方最新净值 + 数量, 计算市值
    holdings = ACCOUNTS[account]
    navs = {}
    for code, (nm, qty) in holdings.items():
        na = Namespace(top=200, json=True, fundcode=None, date=None)
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                fpl.output_direct(code, 'nav', na)
            d = json.loads(buf.getvalue())
            nav = d.get('nav')
            navs[code] = nav
        except Exception:
            navs[code] = None

    for code, (nm, qty) in holdings.items():
        nav = navs.get(code)
        mv = (qty * nav) if nav else None
        na = Namespace(top=200, json=True, fundcode=None, date=None)
        est = None; q = n = 0
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                fpl.output_estimate(code, args.report, na)
            d = json.loads(buf.getvalue())
            est = d['total_contribution_pct']; n = d['holdings']; q = d['quoted']
        except Exception as e:
            print(f'  {code} {nm}: 估算失败 {e}')
            continue
        est_rows.append((code, nm, qty, nav, mv, est, q, n))

    if args.json:
        print(json.dumps([dict(code=c, name=n, qty=q, nav=na,
                               mkt_value=m, est_pct=e, quoted=qq, holdings=nn)
                          for c,n,q,na,m,e,qq,nn in est_rows],
                         ensure_ascii=False, indent=2))
        return

    hdr = '代码    名称              数量   最新净值   市值      今日估算   估值变动(元)'
    print(hdr); print('-'*len(hdr))
    tot_mv = 0; tot_abs = 0
    for code, nm, qty, nav, mv, est, q, n in est_rows:
        if mv is None or est is None:
            continue
        change = mv * est / 100
        tot_mv += mv; tot_abs += change
        print(f'{code}  {nm:<12s} {qty:>5d}  {nav:>8.4f}  {mv:>9,.0f}  {est:>+7.2f}%  {change:>+10,.0f}')
    print('-'*len(hdr))
    print(f'合计持仓市值 {tot_mv:,.0f} ｜ 加权估算今日 {tot_abs/tot_mv*100:+.2f}% ｜ 今日估值变动 {tot_abs:+,.0f} 元')

if __name__ == '__main__':
    main()
