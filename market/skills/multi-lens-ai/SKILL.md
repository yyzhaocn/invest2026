---
name: multi-lens-ai
description: 批量 7 维信号 + 本地 LLM 解读报告：对股票列表/组合持仓/板块成分逐个跑 multi-lens --json，构建信号摘要后调用本地模型（默认 8080 llama.cpp）逐只解读（信号强弱/关键位/操作建议），输出 Markdown 报告。当用户说「用本地模型解读7维」「批量分析持仓并解读」「lens ai review」时使用。反触发：只看信号结果用 multi-lens；只看图用 multi-lens 出图。
---

# multi-lens-ai — 7维信号 × 本地模型解读报告

批量跑 7 维分析后用本地 LLM（8080）逐只解读，生成汇总报告。

## 使用

```bash
python3 /Users/yyz/.agents/skills/stock/multi-lens-ai/scripts/multi-lens-ai.py <代码...> [选项]
python3 multi-lens-ai.py 603435 002709                    # 指定代码
python3 multi-lens-ai.py --account 7维选股                # 读组合持仓全部标的
python3 multi-lens-ai.py --block BK1036 --top 10         # 板块内前N只
```

选项：

- `--account <名>`：读取组合持仓（portfolio show --json）
- `--block BKxxxx`：板块成分（市值排序前 N）
- `--top N`：板块取前 N（默认 10）
- `--url`：本地模型端点（默认 `http://localhost:8080/v1/chat/completions`）
- `--out`：报告路径（默认 `cwd/generated/lens_ai_report.md`）
- `--max-tokens`：模型输出上限（默认 450）

## 流程

1. 对每只标的跑 `multi-lens <code> --json` → 提取 verdict + 非零方向信号
2. 构建 prompt：要求模型分 3 点解读（①信号强弱排序 ②关键支撑/压力位 ③操作建议 ≤80字）
3. 调本地模型（temperature 0.3，curl 子进程——**勿用 urllib/requests**，会走代理导致 502）
4. 汇总 Markdown：每只一节（7维信号 + 本地模型解读）

## 依赖与注意

- 需要本地 llama.cpp 运行在 8080（`switch-model` 切换；模型自动从 `/v1/models` 探测）
- 解读质量：granite-4.1-8B 可正确排序信号与给出关键位（已验证）；13 只约 5-8 分钟（每只 ~20-40s）
- 失败容错：单只 multi-lens 失败或模型调用失败会标注 ⚠️ 并继续，不中断
- 关键：模型调用必须用 curl 子进程（本地 urllib 走系统代理 → HTTP 502）；multi-lens 本身走 sina/东财接口不受影响

## 典型用途

- 组合持仓全量复盘（`--account 7维选股`）
- 板块扫描结果二次解读（`--block`）
- 变盘前夜标的批量确认
