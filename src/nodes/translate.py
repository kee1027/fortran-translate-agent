"""translate / repair 节点：调用 Ollama 微调模型，结构化输出代码。

要点：8B 模型不依赖原生 function calling，用 JSON schema + few-shot 约束输出。
TODO(M0): 实现 translate(state) -> state
TODO(M1): 实现 repair(state) -> state（携带最近 error_history_window 轮错误摘要）
"""
