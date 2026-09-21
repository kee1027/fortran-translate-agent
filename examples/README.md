# 评测示例集

每个子目录一个样例：

```
examples/
└── demo_001/
    ├── source.f            # 原始 Fortran 代码
    ├── input.txt           # 标准输入
    └── expected_output.txt # 参考输出（由原始程序生成）
```

⚠️ 样例必须从未参与微调训练的数据中留出。
