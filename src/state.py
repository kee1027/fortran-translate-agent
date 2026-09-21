"""LangGraph 状态定义：Agent 环路中流转的全部信息。"""
from typing import TypedDict


class TranslationState(TypedDict, total=False):
    source_code: str          # 原始 Fortran 代码
    target_lang: str          # 目标语言（python / c / fortran90）
    current_code: str         # 当前版本翻译结果
    iterations: int           # 已执行的修复轮数
    error_history: list[dict] # 每轮错误 {stage, error, patch_summary}
    compile_ok: bool
    test_ok: bool
    final_status: str         # success / max_iter_reached / oscillation_aborted
