# 03 · 数据规范 v0

> 目标：定义 Fortran→C++ 平行数据的统一格式，使数据可生成、可验证、可去重、可切分、可追溯。  
> 首要原则：一条样本必须对应一个可编译、可运行、可验证的翻译单元。

---

## 1. 数据单元

一条样本由以下内容组成：

- 一段完整的 Fortran 源码或明确的翻译单元；
- 一段等价的 C++17 源码；
- 至少一个测试输入和期望输出；
- 编译、运行和验证元数据；
- 来源、许可、方言、特性标签和切分信息。

不允许把无法独立编译的随机代码片段当作正式训练样本。

## 2. 存储格式

- 训练和评测数据统一使用 JSONL（每行一个 JSON 对象）。
- 大段源码放在 JSON 字符串中；如果后续需要独立文件，导出工具再从 JSONL 生成。
- 每条记录必须有稳定、唯一的 `id`。
- 所有样本必须记录 `source`、`license` 和 `split`。

## 3. 字段规范

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 全局唯一，建议 `f2cpp-000001` |
| `source` | string | 是 | 来源类型或仓库名 |
| `source_url` | string | 否 | 原始链接或本地归档标识 |
| `license` | string | 是 | `MIT`、`BSD-3-Clause`、`public-domain`、`synthetic` 等 |
| `fortran_dialect` | string | 是 | `f77`、`f90`、`f95` |
| `features` | string[] | 是 | 例如 `array`、`do-loop`、`module`、`io` |
| `input_fortran` | string | 是 | 完整 Fortran 源码 |
| `output_cpp` | string | 是 | 完整 C++17 源码 |
| `notes` | string | 是 | 映射说明和风险 |
| `unsupported` | string[] | 是 | 无法可靠翻译的 Fortran 特性，没有则为空数组 |
| `compile_info` | object | 是 | Fortran/C++ 编译命令或编译器 |
| `tests` | object[] | 是 | 测试输入、期望输出和容差 |
| `validation` | object | 是 | 编译、测试和人工复核状态 |
| `split` | string | 是 | `train`、`val`、`test` |
| `reviewed_by` | string | 否 | 人工复核者标识 |
| `tags` | string[] | 否 | 额外检索标签 |

## 4. 测试对象

每个 `tests` 元素：

```json
{
  "name": "basic",
  "input": "5\n1.5 2.25 3.125 4.0 -0.875\n",
  "expected": "   10.000000\n",
  "rel_tolerance": 1.0e-9,
  "abs_tolerance": 1.0e-12,
  "comparison": "numeric_or_text"
}
```

比较模式：

- `text`：逐行严格比较，允许去除行尾空白。
- `numeric`：从输出提取数值，按容差比较。
- `numeric_or_text`：优先数值比较，失败后可按文本比较。
- `custom`：由样本指定的脚本或规则处理，MVP 暂不大量使用。

## 5. 验证状态

```json
{
  "fortran_ok": true,
  "cpp_ok": true,
  "tests_ok": true,
  "reviewed": false
}
```

- `fortran_ok`：Fortran 参考程序编译并运行成功。
- `cpp_ok`：C++ 翻译程序编译并运行成功。
- `tests_ok`：所有测试通过。
- `reviewed`：是否经过人工复核。

只有 `fortran_ok=true`、`cpp_ok=true`、`tests_ok=true` 的样本才允许进入正式训练集；`reviewed=false` 的样本可以进入预训练/冒烟集，但必须在数据卡中标注。

## 6. 数据来源优先级

1. 宽松许可的公开数值代码：Netlib、Rosetta Code、Fortran-lang 生态包、LAPACK 示例。
2. 强模型合成：按语法点定向生成，再由双端编译执行验证。
3. 人工改写：小规模高质量种子，用于校准合成数据。
4. Agent 回放：首轮失败→修复成功的轨迹。
5. 负样本：不支持特性、歧义代码和精度风险。

大规模语料（CodeNet、The Stack 等）只能在核验语言标注、许可和去重质量后加入。

## 7. 去重与切分

- 先按完全相同的源码哈希去重。
- 再做函数名归一化、空白归一化和 n-gram 相似度检查。
- 训练/验证/测试按来源或项目隔离，不能随机按行切分。
- 同一仓库、同一作者连续子程序、同一模板变体尽量放在同一侧。
- 测试集冻结后记录 SHA-256 和样本 ID 列表。

## 8. 质量控制红线

- 没有编译通过的样本不得标记为 `cpp_ok=true`。
- 没有运行验证的样本不得进入正式训练集。
- 合成数据不得绕过双端编译执行验证。
- 浮点样本必须给出容差或说明。
- 不支持特性必须进入 `unsupported`/`notes`，不能静默省略。
- 训练集和测试集不得存在近重复样本。

## 9. 建议目录

```text
data/
├── raw/                 # 原始抓取或生成结果，不直接训练
├── processed/           # 标准化后的 JSONL
├── reviewed/            # 人工复核后的 JSONL
├── splits/
│   ├── train.jsonl
│   ├── val.jsonl
│   └── test.jsonl
└── schema/
    └── translation_sample.schema.json
```

## 10. 最小工作流

```text
收集/生成
 → 标准化为 JSON
 → validate_dataset.py
 → gfortran/g++ 双端编译
 → 测试输入运行与输出对比
 → 去重与切分
 → 人工抽检
 → train/val/test
```
