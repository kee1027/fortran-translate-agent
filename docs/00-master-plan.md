# 00 · 项目总纲与导航

本文件是仓库内的总入口。完整、持续更新的学习与实施主计划在仓库上层：

- [总体学习、实施与汇报计划](../../Fortran转Cpp-Agent-总体学习与实施计划.md)

本仓库内的细化文档：

- [01 · 翻译契约 v0](01-translation-contract.md)
- [03 · 数据规范 v0](03-data-spec.md)
- [04 · 7B LoRA 训练与导出手册](04-training-manual.md)

## 当前 v1.1 决策摘要

| 项目 | 决策 |
|---|---|
| 本地机器 | Intel NUC i7-7000，只做 CPU 推理、数据处理、Prompt 和 Agent 开发 |
| 正式训练 | 2×A800 40GB，PyTorch 2.1 + CUDA 12.1 + Python 3.10 |
| MVP 模型 | Qwen2.5-Coder-7B-Instruct 级 7B 稠密模型 |
| MVP 方法 | A800 单卡 bf16 LoRA；QLoRA 留给 14B/30B 或显存受限场景 |
| Fortran 范围 | 主集：F90/95 自由格式数值子程序；兼容集：少量 F77 固定格式 |
| C++ 范围 | C++17，第一版只依赖标准库 |
| 数据规模 | 30–50 条种子集 → 500–1000 条 MVP 集 → 后补 3k–10k |
| 部署 | 合并 adapter → GGUF Q4_K_M → Ollama |
| Agent | LangGraph 状态机 + Docker 沙箱 + 编译/运行/数值对比 + 修复闭环 |
| 评测 | base few-shot vs LoRA vs LoRA+Agent；先 50–150 条 MVP 留出集 |

## 最短路径

```text
第 1 周：契约 + 种子样本 + 本地 2B 基线 + A800 环境审计
第 2 周：500–1000 条数据 + 7B bf16 LoRA + GGUF + Ollama
第 3 周：LangGraph 翻译→编译→运行→对比→诊断→修复闭环
第 4 周：50–150 条评测 + 指标表 + README + 简历描述
```

## 当前第一批可执行内容

- `docs/01-translation-contract.md`：翻译范围、支持/不支持特性、正确性分层。
- `data/schema/translation_sample.schema.json`：样本 JSON Schema。
- `scripts/validate_dataset.py`：不依赖第三方库的 JSON/JSONL 数据校验器。
- `scripts/a800_env_audit.py`：A800 环境与 PyTorch/CUDA/LoRA 依赖审计。
- `scripts/ollama_smoke.py`：本地 Ollama 结构化翻译冒烟。
- `scripts/run_seed_sample.py`：种子样本双端编译、运行、输出/数值比较。
- `configs/train_lora_7b.yaml`：LLaMA-Factory 风格 7B LoRA 训练配置骨架。
- `examples/seed/001_sum_double/`：首个 F90→C++17 种子样本。
