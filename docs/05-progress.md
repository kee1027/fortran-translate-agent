# 05 · 进度记录

## 2026-09-23 · 第一批与第二批基础

### 已完成

- 翻译契约 v0：`docs/01-translation-contract.md`
- 数据规范 v0：`docs/03-data-spec.md`
- 样本 JSON Schema：`data/schema/translation_sample.schema.json`
- 数据校验器：`scripts/validate_dataset.py`
- LLaMA-Factory 数据转换器：`scripts/convert_to_llamafactory.py`
- A800 环境审计脚本：`scripts/a800_env_audit.py`
- 本地 Ollama 冒烟脚本：`scripts/ollama_smoke.py`
- 种子样本双端编译/运行/比较脚本：`scripts/run_seed_sample.py`
- 输出比较库：`src/eval/compare.py`
- 7B bf16 LoRA 配置骨架：`configs/train_lora_7b.yaml`
- QLoRA 备选配置骨架：`configs/train_lora_7b_qlora.yaml`
- 第一个 F90→C++17 种子样本：`examples/seed/001_sum_double/`
- 第一条真实基线失败案例：`examples/baseline_failures/001_sum_double_missing_includes.md`

### 本地已验证

```bash
python -m py_compile scripts/validate_dataset.py scripts/a800_env_audit.py scripts/ollama_smoke.py scripts/convert_to_llamafactory.py scripts/run_seed_sample.py src/state.py src/llm/schemas.py src/eval/compare.py
python scripts/validate_dataset.py examples/seed/001_sum_double/metadata.json
python -m unittest discover -s tests -q
python scripts/convert_to_llamafactory.py examples/seed/001_sum_double/metadata.json --output data/llamafactory/fortran_cpp_train.jsonl --dataset-name fortran_cpp_train
python scripts/run_seed_sample.py examples/seed/001_sum_double --dry-run
python scripts/ollama_smoke.py --model qwen3.5:2b --num-predict 256 --no-think --require-json
```

结果：

- 9 个单元测试通过；
- 种子 metadata 通过校验；
- ShareGPT 转换成功；
- dry-run 命令生成正确；
- 本地 Ollama 返回合法 JSON；
- 当前真实基线输出缺少 `<iostream>`、`<iomanip>`，且没有保留 `F12.6`，已被记录为失败案例。

### 当前阻塞

- 本机没有 `gfortran` / `g++`，实际双端编译必须在 A800 或 Docker 中执行。
- 本地 Docker CLI 在当前沙箱内无法读取用户 Docker 配置，无法直接验证镜像。
- A800 侧环境尚未实际采集。

### 下一步

1. 在 A800 上运行 `scripts/a800_env_audit.py`；
2. 在 A800 或 Docker 中运行 `scripts/run_seed_sample.py`，更新种子样本 `validation`；
3. 扩充到 30–50 条种子样本；
4. 实现 `src/llm/client.py`、`prompts.py` 与 translate/repair 节点；
5. 实现 `src/sandbox/runner.py`，接入 Docker；
6. 实现最小 LangGraph 闭环 translate→compile→run_compare→diagnose→repair→guard。
