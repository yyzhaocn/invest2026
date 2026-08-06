---
name: my-ip
description: 获取本机对外公网 IP 与网络出口诊断：多源（ipify/ip.sb/ipinfo）交叉验证公网 IP、归属地（如「云南昆明 电信」）、CGNAT 检测（出口是否为私网地址）、本机局域网 IP 与代理环境变量。当用户问「我的 IP 是什么」「是不是被限流了/换 IP」「网络出口/代理状态」时使用。
---

# my-ip — 对外 IP 与网络出口诊断

查询本机公网出口 IP、归属地、CGNAT 状态与代理配置。用于排查「某个服务对当前 IP 限流」（如东方财富行情接口）等网络问题。

## 使用

```bash
python3 market/skills/my-ip/scripts/my-ip.py [--json]
```

参数：

- `--json`：输出 JSON（IP、归属地、CGNAT、局域网 IP、代理）

## 输出示例

```
公网 IP: 116.52.237.72 ｜ 归属: 中国 云南 昆明 电信（ipinfo）
多源一致性: ipify ✓ / ip.sb ✓ / ipinfo ✓
CGNAT: 未检测到（出口为公网地址）
局域网: en0=192.168.31.34
代理: 未配置
```

## 检测逻辑

- **公网 IP**：轮询多个 echo 服务（`api.ipify.org` / `api.ip.sb` / `ipinfo.io/ip`），取多数一致结果；任一服务失败自动跳过
- **归属地**：`ipinfo.io/json`（或 `myip.ipip.net` 中文归属）
- **CGNAT 检测**：若 echo 服务返回私网地址（`192.168.*` / `10.*` / `172.16-31.*` / `100.64-127.*`），提示处于运营商级 NAT（重启路由器无法换 IP）
- **局域网 IP**：`ipconfig getifaddr en0/en1`
- **代理**：检查 `HTTP_PROXY` 等环境变量

## 典型用途

- 排查「XX 接口被限流」：确认当前出口 IP，判断换 IP 手段（VPN / 重启光猫 / 手机热点）
- 验证代理/VPN 是否生效：连接前后各跑一次，对比 IP 变化
