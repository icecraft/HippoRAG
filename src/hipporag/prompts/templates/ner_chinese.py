ner_system = """你的任务是从给定的段落中提取命名实体。
请以 JSON 列表形式返回实体。

你必须仅返回有效的 JSON，不要包含任何额外文本：
{"named_entities": ["实体1", "实体2", ...]}

关键要求：
- 正确识别并提取文本中的所有命名实体，包括人名、地名、组织名、物品名、时间等。
- 保持实体在原文中的语言形式（中文名用中文，英文名用英文）。
- 不要翻译或改写实体名称。

重要：整个响应必须是有效的 JSON。
- 正确转义特殊字符（例如，反斜杠使用 \\\\，字符串内的引号使用 \\"）。
- 不要在字符串值中使用未转义的反斜杠、制表符或控制字符。
- 不要在响应中包含注释、Markdown 格式或代码围栏。
"""

chinese_ner_paragraph = """方源一身残破的碧绿大袍，披头散发，浑身浴血，环顾四周。山风吹得血袍飘荡，如战旗般嚯嚯作响。就这样紧张地对峙了三个时辰，夕阳西下。他本是地球上的华夏学子，机缘巧合穿越到这方世界。"""


chinese_ner_output = """{"named_entities":
    ["方源", "碧绿大袍", "三个时辰", "地球", "华夏"]
}
"""


prompt_template = [
    {"role": "system", "content": ner_system},
    {"role": "user", "content": chinese_ner_paragraph},
    {"role": "assistant", "content": chinese_ner_output},
    {"role": "user", "content": "${passage}"}
]
