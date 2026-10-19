# 07 · 交接文档：移交服务器侧 Kimi CLI

> 交接日期：2026-10-19。本文件面向服务器上的 Kimi CLI——你接替桌面侧 Kimi Work 的副驾驶角色。
> 读完本文件 + `docs/adr/ADR-0001~0005` + `docs/03-data-spec.md` + `docs/04-training-manual.md`，你应该能独立完成 M0.5。

---

## 1. 项目一句话

用 **Ollama 本地部署的微调模型**（Qwen2.5-Coder-7B + LoRA）驱动一个 **LangGraph Agent 环路**（translate→compile→test→diagnose→repair + 护栏），完成 **Fortran（f77/f90/f95）→ C++17** 的自动翻译；项目定位是求职作品，证明"执行类 Agent"能力，与用户的 RAG 项目互补。

## 2. 已定决策（不要重开讨论，除非用户明确要求）

| # | 决策 | 依据 |
|---|---|---|
| 基座模型 | **Qwen2.5-Coder-7B-Instruct** | ADR-0001（取代早期方案的 LLaMA 3.1 8B） |
| 目标语言 | **C++17**（不是 Python） | `docs/03-data-spec.md`（2026-09 定，ADR-0002/0005 已同步修正） |
| 微调方法 | **LoRA（优先 bf16）/ QLoRA（显存受限时）** + **LLaMA-Factory** | ADR-0003，但有重要更新，见 §4.2 |
| 数据 | 强模型 API 合成 70%（gfortran/g++ 双向编译验证）+ Rosetta Code 10% + netlib/LAPACK 20%；形态 = 直译对 70% + 修复对 30% | ADR-0002 |
| 部署 | merge adapter → llama.cpp 转 GGUF → **Q4_K_M** → `ollama create` | ADR-0004 |
| 评测 | **2×2 矩阵**（基座/微调 × 直译/闭环）+ JSON 解析失败率；测试集 50 条、六类语法点各 ≥5、冻结 SHA-256 | ADR-0005 |
| 训练框架 | LLaMA-Factory（YAML 配置驱动，放项目仓库外 `git clone`） | ADR-0003 + `docs/04-training-manual.md` |

## 3. 仓库现状（截至交接时）

- 已提交（commit `886c0cd`）：定稿 v1.0 + ADR-0001~0005 + 9 月的六份 docs（master-plan/contract/data-spec/training-manual/progress/mock-interview）。
- **未提交改动**（用户本地工作区，push 前请用户确认后一并提交）：
  - ADR-0002 / ADR-0005 的"C++17 目标语言修正"；
  - `README.md`、`configs/agent.yaml`、`src/llm/schemas.py`、`src/state.py` 的修改；
  - 未跟踪：`scripts/` 全部、`data/`（schema + llamafactory）、`configs/train_lora_7b.yaml`、`configs/train_lora_7b_qlora.yaml`、`requirements-train.txt`、`examples/seed/`、`examples/baseline_failures/`、`src/eval/compare.py`、`tests/` 新增。
- GitHub 远端：`git@github.com:kee1027/fortran-translate-agent.git`，主分支 `main`。
- 用户的工作习惯：Conventional Commits（feat:/docs:/test:/chore:），每个里程碑一个 feature 分支 + squash merge（沿用其 EEQS 项目习惯）。

## 4. 硬件与环境事实（这些是硬约束，不要凭假设行动）

### 4.1 服务器 GPU

- **6 × NVIDIA RTX 5880 Ada，单卡 48GB**，驱动 580.142，CUDA 13.0。
- 2026-10-19 20:41 快照：6 卡全部空闲（2–5 MiB）。但用户警告"多**人共享，随时可能被占用"——**每次训练前必须 `nvidia-smi` 重新确认**，不要凭历史快照假设。

### 4.2 训练路线更新（覆盖 ADR-0003 的 QLoRA 默认）

- 若训练时单卡有 **≥40GB 可用**（快照所示的空闲状态）：走 **bf16 LoRA 单卡**（`configs/train_lora_7b.yaml`，04 手册主路线，micro_batch 可到 2，比 QLoRA 快且稳定）。
- 若被占用到 **<24GB**：降级 **QLoRA 单卡**（`configs/train_lora_7b_qlora.yaml`，4bit + micro_batch=1 + grad_accum=16 + cutoff_len=4096）。
- **永远不做跨卡分布式**：共享环境可用人卡数随时变化，DDP/deepspeed 会脆断。
- 这是条件化决策：实际训练前由你（Kimi CLI）跑一次 `nvidia-smi`，把可用显存报告给用户并据此选配置；选择结果回填 ADR-0003 附注。

### 4.3 编译工具链

- 用户 Windows 本地**没有 gfortran/g++**；数据双端验证必须在服务器本机（若已装工具链）或 Docker（`gcc:13` 镜像自带 gfortran+g++）中执行。
- **入站第一件事**：`which gfortran g++ docker` 并报告结果，据此确定 `verify_dual_compile.py` 用原生模式还是 `--docker` 模式。

### 4.4 版本陷阱（04 手册的 pin 需要现场复核）

- 04 手册写死 `torch==2.1.2+cu121` + PyTorch 2.1 生态——这是 2023 末的版本，对 CUDA 13.0 驱动虽向后兼容，但**新版 LLaMA-Factory 很可能要求更新的 torch/transformers**。
- 现场原则：**先装最新 LLaMA-Factory，按其 `requirements.txt` 让 pip 解析 torch 版本**（CUDA 13 驱动可跑 cu121/cu126/cu128 构建），不要照搬手册的旧 pin；装完跑 `scripts/a800_env_audit.py --gpu-smoke`（改名后的通用环境审计）确认。把这个偏差和解决结果记进 `docs/05-progress.md`。

## 5. 协作协议（用户明确要求，必须遵守）

1. **用户手操优先**：git、训练启动、API 调用、ollama 操作一律给命令让用户执行；你只直接做只读验证（读文件、跑测试、解析日志）。用户说"你来"才可代劳。
2. **每步 STAR**：背景（在上游决策中的位置）→ 目的（含验收标准）→ 操作（给用户的命令，逐行注释）→ 结论（回填实际数字/输出，失败时分叉建议）。
3. **决策分级**：ADR 级选择（基座、路线、数据配比）必须用户拍板；实现级细节你自行决定。
4. API key 一律走用户侧环境变量（如 `SYNTH_API_KEY`），你不接触明文密钥。

## 6. 当前任务：M0.5（数据与微调）

完整操作清单（含设计思路、充分注释的示例脚本代码、每步验收标准）在 **`docs/08-m0.5操作清单.md`**。要点速览：

```
第 0 步 环境确认（which gfortran g++ docker + nvidia-smi → 定训练路线）
第 1 步 数据合成（scripts/synthesize_dataset.py：语法点矩阵定向造数）
第 2 步 双向编译验证（scripts/verify_dual_compile.py：质量门，阳性对照先行）
第 3 步 修复对生成（scripts/mutate_for_repair.py：规则变异出 5 类 g++ 错误）
第 4 步 去重/切分/冻结（优先级最低，smoke 之后补）
第 5 步 训练（按 §4.2 选 bf16 LoRA 或 QLoRA）
第 6 步 合并 → GGUF Q4_K_M → ollama create → 冒烟
```

**强烈建议的执行纪律**：第 1 步先小批量（每格 5 条、约 30 条）试合成并验证通过率，pass 后再放量到 1000–3000 条——保护用户的 API 预算。每一步的实际数字回填到 `docs/05-progress.md`。

## 7. 不要做的事

- 不要重开已定 ADR（§2），除非用户主动提出。
- 不要在共享 GPU 上做跨卡训练（§4.2）。
- 不要把未过双端验证的样本标 `*_ok=true`（数据规范红线，`docs/03-data-spec.md` §8）。
- 不要绕过用户直接 push GitHub 或调用付费 API。

## 8. 交接完成标志

- [ ] 环境审计结果记录（GPU 可用显存、工具链、torch/transformers/peft 版本）→ `docs/05-progress.md`
- [ ] 训练路线按 §4.2 现场决定并通知用户确认
- [ ] 第 2 步阳性对照（种子样本 `examples/seed/001_sum_double`）PASS
- [ ] 之后每步按 `docs/08-m0.5操作清单.md` 推进并回填进度
