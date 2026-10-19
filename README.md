# Fortran → C++ 翻译 Agent

基于 LangGraph 的「翻译 → 编译 → 执行 → 数值对比 → 诊断 → 修复」闭环系统。目标是用领域 LoRA 微调的轻量代码模型，在本地 Ollama 上完成 Fortran 90/95 数值代码到 C++17 的辅助翻译，并通过编译和数值验证降低“看起来正确”的风险。

## 当前阶段

项目处于 **MVP 第一批落地**：

- 已确定翻译契约 v0：`docs/01-translation-contract.md`
- 已确定数据规范 v0：`docs/03-data-spec.md`
- 已提供数据校验、LLaMA-Factory 转换与双端编译验证脚本
- 已提供 A800 环境审计脚本
- 已提供本地 Ollama 结构化翻译冒烟脚本
- 已提供 7B bf16 LoRA 与 QLoRA 配置骨架
- 已提供第一个 F90→C++17 种子样本和第一条真实基线失败案例

训练与部署主计划见仓库上层的 [总体学习、实施与汇报计划](../../Fortran转Cpp-Agent-总体学习与实施计划.md)，仓库内导航见 `docs/00-master-plan.md`。

## 技术路线

```text
Intel NUC
  └── Ollama CPU 冒烟、数据处理、Prompt / Agent 开发

2×A800 40GB
  └── Qwen2.5-Coder-7B-Instruct
      └── bf16 LoRA（MVP）
          └── 合并 adapter → GGUF Q4_K_M → Ollama

Agent
  └── LangGraph 状态机
      └── Docker 沙箱
          └── gfortran 参考执行 + g++ 候选执行
              └── 输出/数值对比 → diagnose → repair → guard
```

## 架构

```text
Fortran 源码
    ↓
translate ──► compile ──► run_compare ──► ✅ done
    ▲              │             │
    │              │ 失败        │ 差异
    │              ▼             ▼
    └──────── diagnose ──────► repair

护栏：max_iterations / 震荡检测 / 超时 / 资源限制 / JSON 校验
```

## 目录

```text
├── configs/
│   ├── agent.yaml
│   ├── train_lora_7b.yaml
│   └── train_lora_7b_qlora.yaml
├── data/
│   └── schema/translation_sample.schema.json
├── docs/
│   ├── 00-master-plan.md
│   ├── 01-translation-contract.md
│   ├── 03-data-spec.md
│   └── 04-training-manual.md
├── examples/seed/001_sum_double/
├── scripts/
│   ├── a800_env_audit.py
│   ├── convert_to_llamafactory.py
│   ├── ollama_smoke.py
│   ├── run_seed_sample.py
│   └── validate_dataset.py
├── src/
│   ├── graph.py
│   ├── state.py
│   ├── nodes/
│   ├── sandbox/
│   ├── llm/
│   └── eval/
└── tests/
```

## 快速开始

### 1. 校验数据

```bash
python scripts/validate_dataset.py examples/seed/001_sum_double/metadata.json
```

### 2. 双端编译验证（A800 或 Docker）

本机没有 gfortran/g++，可以先 dry-run：

```bash
python scripts/run_seed_sample.py examples/seed/001_sum_double --dry-run
```

在 A800 上：

```bash
python scripts/run_seed_sample.py examples/seed/001_sum_double --engine local --update-metadata
```

或用 Docker：

```bash
python scripts/run_seed_sample.py examples/seed/001_sum_double --engine docker --image gcc:13
```

### 3. 转换为 LLaMA-Factory ShareGPT 格式

```bash
python -m scripts.convert_to_llamafactory \
  examples/seed/001_sum_double/metadata.json \
  --output data/llamafactory/fortran_cpp_train.jsonl \
  --dataset-name fortran_cpp_train
```

### 4. 本地 Ollama 冒烟

当前本地模型为 `qwen3.5:2b`：

```bash
python scripts/ollama_smoke.py --model qwen3.5:2b --require-json
```

### 5. A800 环境审计

在训练机器上执行：

```bash
python scripts/a800_env_audit.py --output artifacts/a800_env_report.json --gpu-smoke
```

### 6. 7B LoRA 训练

训练前阅读 `docs/04-training-manual.md`。核心命令：

```bash
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train configs/train_lora_7b.yaml
```

## MVP 验收指标

最终至少报告：

| 指标 | base few-shot | LoRA | LoRA + Agent |
|---|---:|---:|---:|
| JSON 有效率 | - | - | - |
| 编译成功率 | - | - | - |
| 测试通过率 | - | - | - |
| 数值等价率 | - | - | - |
| 平均修复迭代数 | - | - | - |
| 修复成功率 | - | - | - |

## 边界

- MVP 只覆盖 F90/95 自由格式的数值子程序、函数和简单模块。
- C++ 目标为 C++17，第一版只依赖标准库。
- 不承诺形式化语义等价，只报告在明确测试输入和容差下的结果。
- `COMMON`、`EQUIVALENCE`、复杂指针、OpenMP/MPI 等属于二期。

## License

MIT
