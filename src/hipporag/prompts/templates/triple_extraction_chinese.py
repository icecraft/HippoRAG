from .ner_chinese import chinese_ner_paragraph, chinese_ner_output
from ...utils.llm_utils import convert_format_to_template

ner_conditioned_re_system = """你的任务是根据给定的段落和命名实体列表构建 RDF（资源描述框架）图。
请以 JSON 三元组列表形式返回，每个三元组表示 RDF 图中的一个关系。

请注意以下要求：
- 每个三元组应至少包含列表中的一个命名实体，最好包含两个。
- 明确将代词解析为其具体名称，以保持清晰。
- 三元组中的主语、谓语和宾语应使用原文的语言（中文内容用中文表达，英文人名保持英文）。
- 谓语应简洁明确地描述关系，使用中文。

你必须仅返回以下格式的有效 JSON，不要包含任何额外文本：
{"triples": [["主语1", "谓语1", "宾语1"], ["主语2", "谓语2", "宾语2"], ...]}

重要：整个响应必须是有效的 JSON。
- 正确转义特殊字符（例如，反斜杠使用 \\\\，字符串内的引号使用 \\"）。
- 不要在字符串值中使用未转义的反斜杠、制表符或控制字符。
- 不要在响应中包含注释、Markdown 格式或代码围栏。
"""


ner_conditioned_re_frame = """将以下段落转换为 JSON 格式，包含命名实体列表和三元组列表。
段落：
```
{passage}
```

{named_entity_json}
"""


ner_conditioned_re_input = ner_conditioned_re_frame.format(passage=chinese_ner_paragraph, named_entity_json=chinese_ner_output)


ner_conditioned_re_output = """{"triples": [
            ["方源", "身穿", "碧绿大袍"],
            ["方源", "对峙了", "三个时辰"],
            ["方源", "来自", "地球"],
            ["方源", "身份是", "华夏学子"],
            ["方源", "穿越到", "这方世界"]
    ]
}
"""


prompt_template = [
    {"role": "system", "content": ner_conditioned_re_system},
    {"role": "user", "content": ner_conditioned_re_input},
    {"role": "assistant", "content": ner_conditioned_re_output},
    {"role": "user", "content": convert_format_to_template(original_string=ner_conditioned_re_frame, placeholder_mapping=None, static_values=None)}
]
