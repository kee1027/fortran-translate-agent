"""结构化输出 JSON schema。"""

TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "完整的 C++17 翻译/修复结果"},
        "notes": {"type": "string", "description": "关键映射说明，一句话"},
        "unsupported": {
            "type": "array",
            "items": {"type": "string"},
            "description": "无法可靠翻译的 Fortran 特性",
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "模型自评置信度，不代替编译与测试",
        },
    },
    "required": ["code", "notes", "unsupported", "confidence"],
}
