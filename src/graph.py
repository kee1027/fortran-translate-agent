"""LangGraph 状态图：translate -> compile -> test -> done，失败走 diagnose -> repair。

TODO(M0): 接线最小环路 translate -> compile -> diagnose -> repair
TODO(M2): 接入 test 节点（数值等价验证）
TODO(M3): 接入 guardrails（max_iterations / 震荡检测）
"""


def build_graph():
    """构建并返回编译后的 StateGraph。"""
    raise NotImplementedError("M0: 待实现")


if __name__ == "__main__":
    raise SystemExit("M0: python -m src.graph examples/demo.f")
