#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
my-ip: 获取本机对外公网 IP 与网络出口诊断（多源交叉验证 + CGNAT 检测 + 代理检查）。

用法:
  python3 my-ip.py [--json]
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

ECHO_SERVICES = [
    "https://api.ipify.org",
    "https://api.ip.sb/ip",
    "https://ipinfo.io/ip",
]
GEO_URLS = [
    "https://ipinfo.io/json",
    "https://myip.ipip.net",
]
PRIVATE_PREFIXES = ("10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
                    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
                    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
                    "100.64.", "100.65.", "100.66.", "100.67.", "100.68.", "100.69.",
                    "100.70.", "100.71.", "100.72.", "100.73.", "100.74.", "100.75.",
                    "100.76.", "100.77.", "100.78.", "100.79.", "100.80.", "100.81.",
                    "100.82.", "100.83.", "100.84.", "100.85.", "100.86.", "100.87.",
                    "100.88.", "100.89.", "100.90.", "100.91.", "100.92.", "100.93.",
                    "100.94.", "100.95.", "100.96.", "100.97.", "100.98.", "100.99.",
                    "100.100.", "100.101.", "100.102.", "100.103.", "100.104.", "100.105.",
                    "100.106.", "100.107.", "100.108.", "100.109.", "100.110.", "100.111.",
                    "100.112.", "100.113.", "100.114.", "100.115.", "100.116.", "100.117.",
                    "100.118.", "100.119.", "100.120.", "100.121.", "100.122.", "100.123.",
                    "100.124.", "100.125.", "100.126.", "100.127.")


def is_private(ip: str) -> bool:
    return ip.startswith(PRIVATE_PREFIXES)


def get_public_ip():
    """轮询多个 echo 服务，返回 (ip, results: {service: ip})。"""
    from httpget import httpget
    results = {}
    for url in ECHO_SERVICES:
        try:
            r = httpget(url, timeout=8,
                             headers={"User-Agent": "curl/8.0"})
            r.raise_for_status()
            ip = r.text.strip()
            if ip:
                results[url] = ip
        except Exception:
            continue
    if not results:
        return None, results
    # 多数一致（过滤掉异常的私网回显）
    from collections import Counter
    counter = Counter(results.values())
    return counter.most_common(1)[0][0], results


def get_geo(ip: str):
    """归属地（ipinfo 优先，ipip.net 中文兜底）。"""
    from httpget import httpget
    try:
        r = httpget("https://ipinfo.io/json", timeout=8,
                         headers={"User-Agent": "curl/8.0"})
        r.raise_for_status()
        d = r.json()
        city = d.get("city", ""); region = d.get("region", ""); country = d.get("country", "")
        org = d.get("org", "")
        return f"{country} {region} {city}（{org}）".strip()
    except Exception:
        pass
    try:
        r = httpget("https://myip.ipip.net", timeout=8,
                         headers={"User-Agent": "curl/8.0"})
        r.raise_for_status()
        return r.text.strip().split("来自于")[-1].strip() if "来自于" in r.text else r.text.strip()
    except Exception:
        return None


def get_lan_ips():
    ips = []
    for iface in ("en0", "en1", "en2"):
        try:
            out = subprocess.run(["ipconfig", "getifaddr", iface],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
            if out:
                ips.append(f"{iface}={out}")
        except Exception:
            continue
    return ips


def get_proxy():
    prox = {k: v for k, v in os.environ.items() if "proxy" in k.lower()}
    return prox or None


def main():
    ap = argparse.ArgumentParser(description="本机对外 IP 与网络出口诊断")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ip, sources = get_public_ip()
    geo = get_geo(ip) if ip else None
    cgnat = is_private(ip) if ip else None
    lan = get_lan_ips()
    proxy = get_proxy()

    if args.json:
        print(json.dumps({
            "public_ip": ip,
            "geo": geo,
            "cgnat": bool(cgnat),
            "lan_ips": lan,
            "proxy": proxy,
            "sources": sources,
        }, ensure_ascii=False, indent=2))
        return

    if not ip:
        print("❌ 无法获取公网 IP（网络异常或所有 echo 服务不可达）")
        sys.exit(1)

    if cgnat:
        ip_disp = f"{ip}（⚠️ 私网地址，疑似运营商 CGNAT，重启路由器无法换 IP）"
    else:
        ip_disp = f"{ip}（公网出口）"
    print(f"公网 IP: {ip_disp}")
    if geo:
        print(f"归属地: {geo}")
    agree = len(set(sources.values())) == 1
    srcs = " / ".join(f"{s.split('/')[2]}: {'✓' if v == ip else f'✗({v})'}" for s, v in sources.items())
    print(f"多源交叉: {srcs}（{'一致' if agree else '不一致' }）")
    if cgnat:
        print("⚠️  CGNAT 提示: 出口是运营商私网地址，公网 IP 与大量用户共享，换 IP 需 VPN 或等运营商重分配")
    print(f"局域网: {' '.join(lan) if lan else '（未获取）'}")
    print(f"代理: {'已配置 ' + str(proxy) if proxy else '未配置（直连）'}")


if __name__ == "__main__":
    main()
