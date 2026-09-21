"""结构化输出 JSON schema。"""

TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "翻译/修复后的完整代码"},
        "notes": {"type": "string", "description": "改动说明，一句话"},
    },
    "required": ["code", "notes"],
}
