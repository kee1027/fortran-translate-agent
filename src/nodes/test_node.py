"""test 节点：数值等价验证。

双端执行：原始 Fortran 程序 vs 翻译后程序，同输入、按相对误差容差逐字段比对。
TODO(M2): 实现 equivalence check（configs.agent.yaml: verify.rel_tolerance）
"""
