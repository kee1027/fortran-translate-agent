# Fortran 代码智能翻译 Agent

基于 LangGraph 的「翻译 → 编译 → 数值验证 → 自修复」闭环系统：以本地微调的大语言模型（LLaMA 3.1 8B + LoRA，Ollama 部署）为翻译核心，Docker 沙箱执行生成代码，通过数值等价验证自动判定翻译正确性。

## 架构

```
Fortran 源码
    ↓
translate ──► compile ──► test ──► ✅ done
    ▲            │           │
    │            │ 失败      │ 失败
    │            ▼           ▼
    └──────── diagnose ──► repair

护栏层：max_iterations / 震荡检测 / 超时与资源限制
```

## 技术栈

| 层 | 技术 |
|---|---|
| 编排 | LangGraph（State / Node / Edge） |
| 模型 | Ollama · LLaMA 3.1 8B · LoRA adapter · Q4_K_M 量化 |
| 沙箱 | Docker（断网、只读文件系统、内存/CPU/超时限制） |
| 验证 | 双端执行 + 数值等价对比（相对误差容差判定） |

## 核心指标（M3 评测产出）

| 指标 | baseline（单次直译） | agent（闭环） |
|---|---|---|
| compile_rate | - | - |
| equiv_rate（数值等价通过率） | - | - |
| pass@1 / pass@3 | - | - |
| avg_iterations | - | - |

## 快速开始

```bash
# 1. 启动模型服务
ollama serve

# 2. 构建沙箱镜像
docker build -t fortran-sandbox src/sandbox/

# 3. 翻译单个文件
python -m src.graph examples/demo.f

# 4. 跑评测（baseline vs agent 对比）
python -m src.eval.run_eval
```

## 项目结构

```
├── configs/agent.yaml      # 护栏与容差等全部可调参数
├── src/
│   ├── graph.py            # LangGraph 状态图
│   ├── state.py            # TranslationState
│   ├── nodes/              # translate / compile / test / diagnose / guardrails
│   ├── sandbox/            # Docker 执行环境
│   ├── llm/                # Ollama 客户端、prompt、结构化输出 schema
│   └── eval/               # 评测集、指标、对比脚本
├── tests/
└── examples/               # Fortran 示例 + 参考输入输出
```

## License

MIT
