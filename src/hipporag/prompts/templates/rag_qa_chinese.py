# 中文 RAG QA Prompt 模板

one_shot_rag_qa_docs = (
    """维基百科标题: 最后一匹马\n《最后一匹马》（西班牙语：El último caballo）是一部1950年的西班牙喜剧电影，由埃德加·内维尔执导，费尔南多·费尔南·戈麦斯主演。\n"""
    """维基百科标题: 南安普顿\n南安普顿大学成立于1862年，并于1952年获得皇家宪章成为大学，拥有超过22,000名学生。该大学在2010年世界大学学术排名中位列全球前100名研究型大学。\n"""
    """维基百科标题: 方源\n方源身穿一件残破的碧绿色长袍，头发散乱，浑身是血，环顾四周。山风吹得他的血袍飘扬，如同战旗般猎猎作响。他原本是地球上的一名华夏学子，因缘际会穿越到了这个世界。\n"""
)

one_shot_ircot_demo = (
    f'{one_shot_rag_qa_docs}'
    '\n\n问题: '
    "方源穿的是什么颜色的袍子？"
    '\n思考: '
    f"根据文档描述，方源身穿一件残破的碧绿色长袍。所以答案是：碧绿色。"
    '\n\n'
)

rag_qa_system = (
    '你是一个高级阅读理解助手，你的任务是仔细分析文本段落和相应的问题。'
    '你的回答从"思考："开始，在那里你将逐步分解推理过程，说明你是如何得出结论的。'
    '最后以"答案："结尾，给出简洁、明确的回答，不需要额外的阐述。'
)

one_shot_rag_qa_input = (
    f"{one_shot_rag_qa_docs}"
    "\n\n问题: "
    "方源穿的是什么颜色的袍子？"
    '\n思考: '
)

one_shot_rag_qa_output = (
    "根据文档描述，方源身穿一件残破的碧绿色长袍。"
    "\n答案：碧绿色。"
)

prompt_template = [
    {"role": "system", "content": rag_qa_system},
    {"role": "user", "content": one_shot_rag_qa_input},
    {"role": "assistant", "content": one_shot_rag_qa_output},
    {"role": "user", "content": "${prompt_user}"}
]
