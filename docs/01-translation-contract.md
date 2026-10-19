# 01 · Fortran → C++ 翻译契约 v0

> 状态：MVP 草案  
> 目标：在短周期内定义清晰、可编译、可执行、可评测的翻译边界。  
> 主范围：Fortran 90/95 自由格式数值子程序、函数和简单模块。  
> 兼容范围：少量 Fortran 77 固定格式示例。  
> 目标语言：C++17，第一版只依赖标准库。

---

## 1. 翻译输入

每个翻译单元必须尽量提供：

| 字段 | 必需 | 说明 |
|---|---|---|
| `fortran_code` | 是 | 完整、可编译的 Fortran 程序、子程序、函数或模块 |
| `dialect` | 是 | `f77`、`f90`、`f95` |
| `entry_points` | 是 | 需要保留的主程序、函数或子程序接口 |
| `compile_flags` | 否 | 例如 `-std=f2008 -O0 -Wall -Wextra` |
| `run_inputs` | 否 | 标准输入或参数 |
| `expected_outputs` | 否 | 参考 Fortran 运行结果 |
| `constraints` | 否 | 禁止第三方库、保留函数名、精度要求等 |

## 2. 翻译输出

模型必须输出 JSON：

```json
{
  "code": "完整的 C++17 代码",
  "notes": "关键映射说明",
  "unsupported": ["无法可靠翻译的 Fortran 特性"],
  "confidence": "high|medium|low"
}
```

字段规则：

- `code`：必须是完整、可编译的 C++17 源码，不包含 Markdown 代码围栏。
- `notes`：说明索引、列主序、精度、接口和 I/O 的关键变化。
- `unsupported`：没有则为空数组；不得静默省略。
- `confidence`：只表示模型自评，不代替编译和测试结果。

## 3. 正确性分层

| 等级 | 名称 | 判据 |
|---|---|---|
| L0 | 可编译 | C++ 代码可被目标编译器接受 |
| L1 | 可执行 | 程序能正常启动并退出 |
| L2 | 测试通过 | 给定输入下，输出满足测试协议 |
| L3 | 数值等价 | 浮点输出在相对/绝对容差内 |
| L4 | 人工复核 | 接口、副作用、边界、内存和精度通过人工检查 |

项目报告必须区分这些等级，不能把 L0 说成“翻译正确”。

## 4. 首版支持范围

### 4.1 Fortran 语法

- `PROGRAM`、`SUBROUTINE`、`FUNCTION`
- 简单 `MODULE` 与 `USE`
- 显式类型声明与 `IMPLICIT NONE`
- `INTEGER`、`REAL`、`DOUBLE PRECISION`、`COMPLEX`、`LOGICAL`、`CHARACTER`
- 一维和多维数组
- `DO`、`DO WHILE`、块 `IF`、`SELECT CASE`
- 基本算术、比较和逻辑表达式
- `INTENT(IN)`、`INTENT(OUT)`、`INTENT(INOUT)`
- 常用数学内置函数
- 简单的列表导向或格式化 I/O

### 4.2 C++ 目标

- C++17
- 标准库：`<iostream>`、`<vector>`、`<array>`、`<cmath>`、`<algorithm>`、`<numeric>`、`<string>`、`<iomanip>`、`<limits>` 等
- 第一版不依赖 Eigen、xtensor、OpenMP、MPI
- 函数和类命名优先保留 Fortran 过程名的可读映射
- 所有输入、数组边界和类型转换必须显式

## 5. 必须遵守的映射规则

### 5.1 数组与索引

Fortran 数组默认 1-based，C++ 默认 0-based。首版统一采用：

```cpp
const int idx = i - 1;
```

多维数组若直接使用 `std::vector` 扁平化存储，必须显式给出列主序索引：

```text
Fortran: a(i, j), dimensions (n, m)
C++:     a[(j - 1) * n + (i - 1)]
```

如果使用包装类，则包装类必须提供边界检查和清晰的 `operator()` 语义。不得依赖“看起来像 Fortran”的隐式行为。

### 5.2 循环

```fortran
do i = lo, hi, step
```

翻译为：

```cpp
for (int i = lo; step > 0 ? i <= hi : i >= hi; i += step) {
}
```

正步长和负步长都要覆盖测试。

### 5.3 类型与精度

| Fortran | C++ 建议 |
|---|---|
| `INTEGER` | `int` 或 `int32_t`，按范围决定 |
| `INTEGER(8)` | `int64_t` |
| `REAL` | `float`，并在 notes 中注明 |
| `DOUBLE PRECISION` | `double` |
| `REAL(8)` | `double` |
| `COMPLEX` | `std::complex<float>` 或 `std::complex<double>` |
| `LOGICAL` | `bool` |
| `CHARACTER` | `std::string`，固定长度语义在 notes 中说明 |

### 5.4 过程与参数

- `INTENT(IN)`：优先 `const T&` 或值传递。
- `INTENT(OUT)`：优先 `T&`，调用前不要求有意义初值。
- `INTENT(INOUT)`：优先 `T&`。
- 数组参数：优先 `std::vector<T>&` 或显式 `std::span` 风格封装。
- 函数返回值：保留原语义；Fortran 的副作用不得被悄悄移除。
- 可选参数：首版只支持能通过重载或 `std::optional` 清晰表达的简单情况。

### 5.5 模块和全局状态

- `MODULE`：优先映射到 `namespace`。
- 模块变量：优先映射到显式结构体或单例状态对象，不散落全局变量。
- `SAVE`：映射为函数内 `static` 或显式状态对象，并在 notes 中说明重入风险。
- `COMMON`：首版只做简单结构体映射，复杂布局和跨文件共享标记为高风险。
- `BLOCK DATA`：首版不支持自动翻译，返回 `unsupported`。
- `EQUIVALENCE`：首版不支持自动翻译，返回 `unsupported`。

### 5.6 I/O

- 列表导向输入：用 `std::cin`，但必须处理读取失败。
- 列表导向输出：用 `std::cout`，但格式必须与测试协议一致。
- 格式化输出：能映射则映射；无法保证格式一致时，输出结构化数值，并在 notes 中说明。
- 文件 I/O：首版只支持简单顺序文件；单元号语义不直接复制。
- 字符串尾部空格、固定宽度和默认格式差异必须显式处理。

### 5.7 内置函数

常见映射：

| Fortran | C++ |
|---|---|
| `ABS` | `std::abs` |
| `SQRT` | `std::sqrt` |
| `SIN/COS/TAN` | `std::sin/std::cos/std::tan` |
| `EXP/LOG` | `std::exp/std::log` |
| `MAXVAL/MINVAL` | `std::max_element/std::min_element` |
| `SUM` | `std::accumulate` |
| `DOT_PRODUCT` | `std::inner_product` |
| `MATMUL` | 显式三重循环或后续引入数值库 |

注意：Fortran 的 `MOD`、整数除法、负数和浮点边界语义与 C++ 不完全相同，必须单独测试。

## 6. 首版明确不支持或需要人工确认

- `EQUIVALENCE`
- 复杂 `COMMON`/`BLOCK DATA`
- 复杂指针别名和可分配数组生命周期
- `GOTO` 与算术标签的复杂跳转
- 内部过程、递归内部函数的高级用法
- Coarray、OpenMP、OpenMP target、MPI
- 复杂格式化 I/O 和平台相关单元号
- 依赖编译器扩展、预处理器、`INCLUDE` 的隐式代码
- 复杂 C 互操作和未定义行为
- 依赖未定义求值顺序的程序

遇到不支持项时，必须返回 `unsupported`，不得生成“看起来能跑”的错误代码。

## 7. 测试协议

每个种子样本或评测样本至少包含：

```text
input.txt          程序标准输入
expected_output.txt 参考 Fortran 输出
metadata.json      方言、特性、编译、运行和容差信息
```

比较规则：

- 整数、字符串：严格比较，必要时去除行尾空白。
- 浮点数：先用相对误差，再用绝对误差兜底。
- NaN/Inf：必须显式定义是否允许。
- 多行输出：按行和字段对齐比较，不能只看最终总和。
- 随机程序：固定随机种子，或使用统计容差。
- 编译优化：参考 Fortran 和 C++ 使用相同或明确记录的优化级别。

默认容差：

```yaml
rel_tolerance: 1.0e-9
abs_tolerance: 1.0e-12
```

如果源程序本身存在明显的舍入累积，可在样本 metadata 中覆盖，但必须说明理由。

## 8. 代码审查清单

- [ ] 数组维度、下界和列主序是否正确？
- [ ] 循环边界和步长是否正确？
- [ ] 整数除法、取模和负数行为是否一致？
- [ ] 浮点类型和精度是否合理？
- [ ] 参数传递是否保留 `INTENT` 语义？
- [ ] 模块变量和 `SAVE` 状态是否被显式表达？
- [ ] 文件 I/O 和格式化输出是否可验证？
- [ ] 不支持项是否进入 `unsupported`？
- [ ] 代码是否只依赖 C++17 标准库？
- [ ] 是否有测试可以证明翻译正确？

## 9. 版本演进

- v0：F90/95 数值子程序，标准输入输出，简单模块。
- v1：加入更完整的 F77 固定格式兼容、`COMMON` 简单映射、文件 I/O。
- v2：加入 `EQUIVALENCE`、指针别名、OpenMP/MPI 和多文件工程。
- v3：加入形式化或半形式化验证、性能对比和工程级迁移。
