# 示例与基线失败案例

## 种子样本

`examples/seed/` 存放用于校准数据格式、编译流程和评测协议的小样本。每个样本包含：

```text
001_sum_double/
├── fortran/main.f90        # 原始 Fortran
├── cpp/main.cpp            # 参考 C++ 翻译
├── input.txt               # 标准输入
├── expected_output.txt     # 参考输出
└── metadata.json           # 数据规范字段
```

当前种子样本尚未在 A800 或 Docker 沙箱中完成双端编译验证，因此 `validation.*` 保持 `false`。迁移到 A800 后执行：

```bash
python scripts/run_seed_sample.py examples/seed/001_sum_double --engine local --update-metadata
```

验证通过后再将样本移入正式数据目录。

## 基线失败案例

`examples/baseline_failures/` 记录未微调模型的真实失败输出，用于：

- 构建 Agent 修复回归集；
- 生成“编译错误 → 修复”的训练样本；
- 对比微调前后的改善；
- 检查模型自评置信度是否可靠。

## 使用规则

- 种子样本可以进入冒烟集，但不能直接进入正式训练集，除非完成编译和测试验证。
- 评测样例必须与训练样例按来源/项目隔离，禁止近重复泄漏。
