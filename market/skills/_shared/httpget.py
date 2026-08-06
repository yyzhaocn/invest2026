#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP GET 帮手（requests 优先，curl 子进程兜底）。

背景：2026-08-06 起，本机出口网络对 Python 的 TLS 指纹（JA3）做重置，
requests/urllib 连接东方财富（push2/push2delay/push2his）与新浪全部
Connection reset by peer，而 curl 可正常访问。本模块先试 requests，
失败自动改用 curl 子进程，返回与 requests.Response 兼容的对象
（.text / .json() / .status_code / .raise_for_status() / .ok）。
"""
import json
import subprocess
import urllib.parse


class _Resp:
    """兼容 requests.Response 的最小对象。"""

    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
        self.ok = 200 <= status_code < 400

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


def httpget(url, params=None, headers=None, timeout=20):
    """GET url，返回 requests.Response 兼容对象。"""
    headers = headers or {}
    try:
        import requests
        resp = requests.get(url, params=params, timeout=timeout, headers=headers)
        resp.raise_for_status()
        return resp
    except Exception:
        pass
    cmd = ["curl", "-sS", "-f", "--max-time", str(int(timeout) + 10)]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    cmd.append(url)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 20)
        if p.returncode == 0:
            return _Resp(p.stdout, 200)
        return _Resp("", 0)
    except Exception:
        return _Resp("", 0)
