# 04 · 7B LoRA 训练与导出手册

> 目标硬件：2×A800 40GB  
> MVP 路径：单卡 7B bf16 LoRA → 合并 adapter → GGUF Q4_K_M → Ollama  
> 环境：PyTorch 2.1 + CUDA 12.1 + Python 3.10  
> 原则：先跑通，后调参；先 7B，后 14B/30B。

---

## 1. 训练前检查

在 A800 机器上执行：

```bash
nvidia-smi
python -V
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.device_count())"
nvcc -V
df -h
```

仓库中的审计脚本会生成 JSON 报告：

```bash
python scripts/a800_env_audit.py --output artifacts/a800_env_report.json --gpu-smoke
```

重点确认：

- 两张 A800 都能被 PyTorch 看到；
- `torch.cuda.is_available()` 为 `True`；
- `torch.cuda.device_count()` 为 `2`；
- bf16 可用；
- 磁盘至少有约 150–250GB 可用空间；
- `transformers`、`peft`、`trl`、`accelerate`、`datasets` 可用。

## 2. 创建训练环境

建议使用独立 conda 环境：

```bash
conda create -n fta-train python=3.10 -y
conda activate fta-train
python -m pip install --upgrade pip
```

安装 PyTorch 2.1 + CUDA 12.1：

```bash
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu121
```

安装训练依赖：

```bash
pip install -r requirements-train.txt
```

> 注意：不要把 LLaMA-Factory 的 `[torch]` extra 当成默认安装方式，避免它把 PyTorch 2.1 替换成其他版本。先安装并确认 torch，再安装训练框架。

## 3. 安装 LLaMA-Factory

推荐把 LLaMA-Factory 放在项目外部：

```bash
git clone https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e .
```

安装后确认：

```bash
llamafactory-cli version
python -c "import torch, transformers, peft; print(torch.__version__, transformers.__version__, peft.__version__)"
```

如果版本冲突，优先保持 PyTorch 2.1 和现有 CUDA 12.1 不变，再选择兼容的 transformers/peft/trl 版本。

## 4. 数据转换

项目内部数据格式见 `docs/03-data-spec.md`。转成 LLaMA-Factory ShareGPT 格式：

```bash
python -m scripts.convert_to_llamafactory \
  data/reviewed/train.jsonl \
  --output data/llamafactory/fortran_cpp_train.jsonl \
  --dataset-name fortran_cpp_train

python -m scripts.convert_to_llamafactory \
  data/reviewed/val.jsonl \
  --output data/llamafactory/fortran_cpp_val.jsonl \
  --dataset-name fortran_cpp_val
```

把生成的两个 JSONL 文件复制到 LLaMA-Factory 的 `data/` 目录，并合并 `dataset_info.json`，或在 LLaMA-Factory 的 `data/dataset_info.json` 中加入同样配置。

当前 MVP 配套脚本位于：

- `scripts/validate_dataset.py`
- `scripts/convert_to_llamafactory.py`

## 5. 训练配置

项目中的配置骨架：

- `configs/train_lora_7b.yaml`：7B bf16 LoRA，MVP 主路线。
- `configs/train_lora_7b_qlora.yaml`：14B/30B QLoRA 备选，暂不优先。

7B 默认参数：

| 参数 | 值 |
|---|---|
| LoRA rank | 32 |
| LoRA alpha | 64 |
| dropout | 0.05 |
| target modules | all |
| max length | 4096 |
| micro batch | 2 / GPU |
| gradient accumulation | 16 |
| learning rate | 1e-4 |
| epochs | 2 |
| precision | bf16 |
| gradient checkpointing | true |

单卡启动：

```bash
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train /path/to/configs/train_lora_7b.yaml
```

双卡时先确认单卡跑通，再切 DDP：

```bash
CUDA_VISIBLE_DEVICES=0,1 llamafactory-cli train /path/to/configs/train_lora_7b.yaml
```

如果显存不足，按顺序调整：

1. `per_device_train_batch_size: 2 → 1`
2. `cutoff_len: 4096 → 2048`
3. 确认 `gradient_checkpointing: true`
4. 确认 `bf16: true`
5. 仍不足时，再考虑 QLoRA，而不是先换更大模型

## 6. 训练过程要监控什么

不要只看 loss。每 200 step 至少记录：

- 训练 loss 和验证 loss；
- 学习率；
- 梯度范数；
- 单步耗时和显存峰值；
- 留出集的 JSON 解析成功率；
- 留出集的编译成功率；
- 留出集的测试通过率；
- 生成代码是否截断或重复。

推荐保存：

```text
outputs/qwen2.5-coder-7b-lora/
├── adapter_config.json
├── adapter_model.safetensors
├── tokenizer files
├── trainer_state.json
├── training_args.bin
├── train_config.json
└── logs/
```

同时保存：

- 数据 SHA-256；
- 训练配置副本；
- `pip freeze > pip_freeze.txt`；
- git commit（如果环境允许）；
- GPU 型号和显存；
- 训练耗时。

## 7. 合并 adapter

训练完成后先把 LoRA adapter 合并成完整 Hugging Face 模型。LLaMA-Factory 的 export 命令随版本略有差异，常见写法：

```bash
llamafactory-cli export \
  --model_name_or_path Qwen/Qwen2.5-Coder-7B-Instruct \
  --adapter_name_or_path outputs/qwen2.5-coder-7b-lora \
  --template qwen \
  --finetuning_type lora \
  --export_dir models/qwen2.5-coder-7b-fortran-merged \
  --export_size 2 \
  --export_legacy_format false
```

导出后检查：

```bash
ls models/qwen2.5-coder-7b-fortran-merged
python -c "from transformers import AutoTokenizer; t=AutoTokenizer.from_pretrained('models/qwen2.5-coder-7b-fortran-merged'); print(t)"
```

## 8. 转换 GGUF

使用 llama.cpp 的转换脚本。先准备：

```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
python -m pip install -r requirements.txt
```

转换：

```bash
python convert_hf_to_gguf.py \
  ../models/qwen2.5-coder-7b-fortran-merged \
  --outfile ../models/qwen2.5-coder-7b-fortran-f16.gguf \
  --outtype f16
```

量化 Q4_K_M：

```bash
./llama-quantize \
  ../models/qwen2.5-coder-7b-fortran-f16.gguf \
  ../models/qwen2.5-coder-7b-fortran-q4_k_m.gguf \
  Q4_K_M
```

如果 `llama-quantize` 不存在，先按 llama.cpp 当前版本的构建说明编译：

```bash
cmake -B build
cmake --build build --config Release -j
```

## 9. Ollama 加载

创建 Modelfile：

```text
FROM ./qwen2.5-coder-7b-fortran-q4_k_m.gguf
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
```

创建模型：

```bash
ollama create fortran-translator:7b-q4 -f Modelfile
ollama list
ollama show fortran-translator:7b-q4
```

本地冒烟：

```bash
python scripts/ollama_smoke.py --model fortran-translator:7b-q4 --require-json
```

## 10. MVP 验收标准

- [ ] 7B bf16 LoRA 在单张 A800 40GB 上训练完成；
- [ ] 保存 adapter、训练日志和完整配置；
- [ ] 合并模型可以正常加载；
- [ ] GGUF Q4_K_M 生成成功；
- [ ] Ollama 能加载并返回 JSON；
- [ ] 至少 50 条留出集完成 base vs LoRA 对比；
- [ ] 记录微调前后的 JSON 解析成功率和编译成功率；
- [ ] README 能复现训练和部署命令。

## 11. 常见问题

### 11.1 显存不足

先把 micro batch 降到 1，再降 `cutoff_len`，确认梯度检查点和 bf16。不要先升级模型。

### 11.2 bitsandbytes 与 CUDA 12.1 不兼容

MVP 7B 不需要 QLoRA，直接使用 bf16 LoRA。QLoRA 留给后续 14B/30B。

### 11.3 LLaMA-Factory 安装后 torch 被替换

重新安装 `torch==2.1.2+cu121`，并使用不包含 `[torch]` extra 的安装方式。训练前重新运行 `scripts/a800_env_audit.py`。

### 11.4 GGUF 转换失败

先确认合并模型能被 Transformers 正常加载，再确认 llama.cpp 版本支持该模型架构。若 7B 转换失败，先在 A800 上用 Hugging Face 版本完成评测，不阻塞 Agent 开发。

### 11.5 训练 loss 下降但编译率不升

优先检查：

- 数据是否经过双端编译验证；
- 目标输出是否严格为 JSON；
- 训练样本是否包含足够的编译错误修复对；
- 是否存在数据泄漏或格式错误；
- 是否只学到了 JSON 外壳而没有学到代码。
