"""LangGraph 状态定义：Agent 环路中流转的全部信息。"""
from typing import TypedDict


class TranslationState(TypedDict, total=False):
    source_code: str          # 原始 Fortran 代码
    source_dialect: str       # f77 / f90 / f95
    target_lang: str          # 当前固定为 cpp
    cpp_standard: str         # c++17
    current_code: str         # 当前版本 C++ 翻译结果
    notes: str                # 模型给出的映射说明
    unsupported: list[str]    # 模型标记的暂不支持特性
    confidence: str           # high / medium / low
    iterations: int           # 已执行的修复轮数
    error_history: list[dict] # 每轮错误 {stage, error, patch_summary}
    compile_ok: bool
    test_ok: bool
    final_status: str         # success / max_iter_reached / oscillation_aborted
