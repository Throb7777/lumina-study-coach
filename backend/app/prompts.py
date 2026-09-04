from app.models import DailyRecord, Exercise, ExerciseItem, ExerciseItemType, GuidedReflection

MARKDOWN_MATH_RULES = """输出格式要求：
- 使用清晰的 Markdown，不要在最外层包裹 Markdown 代码块
- 行内公式使用 `$...$`，独立公式块使用 `$$...$$`
- 不使用 `\\(...\\)` 或 `\\[...\\]` 公式分隔符
- 分数必须写成 `\\frac{分子}{分母}`，不要省略花括号
"""

STRUCTURED_RESULT_RULES = """请同时返回：
- `display_markdown`：直接展示给学习者的完整 Markdown
- `handoff`：供后续流程使用的精简结构化结论，不要复制整篇展示内容
- 使用参考材料形成判断时，在展示内容中用 `[材料标题，页码/时间段/网页正文]` 标注依据
- `handoff.source_refs` 只保留本次实际使用过的材料分块；每条返回 `material_id`、
  `chunk_positions` 和一句简短 `evidence_summary`，编号必须来自材料中的 `[M编号:C编号]`
- 没有直接使用材料时，`handoff.source_refs` 返回空数组
- JSON 字符串中的反斜杠必须正确转义；LaTeX 命令的反斜杠必须写成 `\\`，不得输出控制字符
输出必须符合系统指定的 JSON 结构。"""

NOTE_STRUCTURED_RESULT_RULES = """请同时返回：
- `display_markdown`：直接展示给学习者的完整 Markdown 笔记
- 笔记正文不要输出材料引用、来源标记或来源清单
- `handoff`：供后续流程使用的精简结构化结论，不要复制整篇展示内容
- `handoff.source_refs` 只保留本次实际使用过的材料分块；每条返回 `material_id`、
  `chunk_positions` 和一句简短 `evidence_summary`，编号必须来自材料中的 `[M编号:C编号]`
- 没有直接使用材料时，`handoff.source_refs` 返回空数组
- JSON 字符串中的反斜杠必须正确转义；LaTeX 命令的反斜杠必须写成 `\\`，不得输出控制字符
输出必须符合系统指定的 JSON 结构。"""


def deterministic_choice_verdict(item: ExerciseItem) -> str | None:
    if item.item_type not in {
        ExerciseItemType.SINGLE_CHOICE,
        ExerciseItemType.MULTIPLE_CHOICE,
    }:
        return None
    expected = item.answer_key.get("selected_options")
    if not isinstance(expected, list) or item.response is None:
        return None
    expected_set = {str(option) for option in expected}
    selected_set = set(item.response.selected_options)
    return "correct" if selected_set == expected_set else "incorrect"


def daily_summary_prompt(source: str) -> str:
    return f"""你是一名学习流程教练。请把今天的学习成果整理为供下一次学习读取的紧凑摘要。
这不是展示性长笔记，不要添加未经提供或参考材料支持的事实，也不要继续追问。

【今日完整记录】
{source}

`display_markdown` 应简洁包含：
- 今天实际推进到哪里
- 已确认的核心概念、定义或推导
- 评阅和批改指出的主要修正
- 尚未解决的问题与下一次衔接点
- 有错题时概括错误模式，没有则省略

总长度尽量控制在 800 个中文字符以内。材料引用仅在确实用于核对时保留。
同时返回更新后的 `section_memory` 和 `chapter_memory`。它们是完整的当前版本，
需要合并上下文中已有记忆与今日新增成果，不得丢失仍然有效的旧内容。

{MARKDOWN_MATH_RULES}
{STRUCTURED_RESULT_RULES}
"""


def recall_questions_prompt(
    record: DailyRecord,
    source_record: DailyRecord | None = None,
) -> str:
    source_label = (
        f"{source_record.study_date} · {source_record.section.title}"
        if source_record is not None
        else "暂无上次已完成学习"
    )
    source_scope = source_record.study_material_scope if source_record is not None else ""
    return f"""你是一名善于追问的学习教练。学习者先做了一次不看材料的自由回忆。
请只围绕上一次已完成学习及其可靠材料，生成恰好 3 个有方向、可直接作答的定向问题。

回顾对象：{source_label}
上次学习范围：{source_scope or "未填写"}
学习者的自由回忆：
{record.recall_last_learned or "未填写"}

三个问题应分别尽量覆盖：
1. 相关知识或核心概念之间的关系；
2. 关键条件、边界、步骤或推导；
3. 一个具体例子、反例或迁移应用。

要求：
- 问题必须针对学习者实际写出的内容，指出明确对象，不得让学习者“任选一个主题/场景/研究背景”；
- 不得考查当前即将学习但上次尚未学习的内容；
- 每个问题只问一个主要任务，单独阅读即可理解；
- 不要在问题中泄露答案，也不要评价学习者；
- `id` 依次使用 `q1`、`q2`、`q3`；
- `focus` 用一句短语说明该问题检查的知识点；
- 输出必须严格符合系统指定的 JSON 结构。
"""


def reconstruction_questions_prompt(record: DailyRecord) -> str:
    return f"""你是一名主动学习教练。学习者已用自己的话重构了本次内容。
请根据其重构和可靠材料，生成恰好 3 个有方向、可直接作答的定向问题。

学习范围：{record.study_material_scope or "未填写"}
学习者的自由重构：
{record.reconstruct_main_learning or "未填写"}

三个问题应分别尽量覆盖：
1. 学习者表述中缺少的关键概念、结构或因果链；
2. 重要定义、适用条件、步骤或数学关系；
3. 一个已指定对象和条件的具体应用、比较或检验。

要求：
- 必须针对学习者实际写出的内容补足方向，不得让学习者“任选一个主题/系统/研究背景”；
- 每个问题只问一个主要任务，题面给足对象、条件和交付物；
- 不要在问题中泄露答案，也不要评价学习者；
- `id` 依次使用 `q1`、`q2`、`q3`；
- `focus` 用一句短语说明该问题检查的知识点；
- 输出必须严格符合系统指定的 JSON 结构。
"""


def guided_reflection_review_prompt(
    record: DailyRecord,
    reflection: GuidedReflection,
    source_record: DailyRecord | None = None,
) -> str:
    seed_label = "自由回忆" if reflection.kind.value == "recall" else "自由重构"
    seed = (
        record.recall_last_learned
        if reflection.kind.value == "recall"
        else record.reconstruct_main_learning
    )
    answers = reflection.answers
    source_label = (
        f"{source_record.study_date} · {source_record.section.title}"
        if reflection.kind.value == "recall" and source_record is not None
        else record.section.title
    )
    source_scope = (
        source_record.study_material_scope
        if reflection.kind.value == "recall" and source_record is not None
        else record.study_material_scope
    )
    question_blocks = []
    for question in reflection.questions:
        question_id = str(question.get("id", ""))
        question_blocks.append(
            f"问题：{question.get('question_markdown', '')}\n"
            f"学习者回答：{answers.get(question_id, '') or '未回答'}"
        )
    return f"""你是一名严谨的学习教练。
请综合评阅学习者的{seed_label}和 3 个定向问题回答。
不要继续追问，也不要替学习者重写整份笔记。

评阅对象：{source_label}
学习范围：{source_scope or "未填写"}
学习者的{seed_label}：
{seed or "未填写"}

定向问题与回答：
{chr(10).join(question_blocks)}

展示内容按以下结构组织：
1. 已经理解准确、表达清楚的部分；
2. 明显遗漏、混淆或条件不完整的部分；
3. 结合可靠材料给出的关键纠正；
4. 一条具体、可执行的后续复习建议。

同时对 q1、q2、q3 分别返回结构化评阅：
- `verdict` 只能是 correct、partial 或 incorrect；
- `feedback_markdown` 必须对应该题实际回答，指出判断依据；
- 回答错误或不完整时给出正确思路，但不要扩写成整份课程笔记；
- `display_markdown` 只放三题之外的整体总结，避免重复逐题反馈。
- `feedback_markdown` 和 `display_markdown` 中的短单行公式必须使用行内公式，
  并与“可写为”“可得”“满足”等引导语放在同一段；只有矩阵、分情况表达、
  多行推导或确实过长的公式才使用独立公式块。

{MARKDOWN_MATH_RULES}
{STRUCTURED_RESULT_RULES}
"""


def recall_review_prompt(record: DailyRecord, previous_records: list[DailyRecord]) -> str:
    del previous_records
    return f"""你是一名严谨的学习流程评阅助手。请评价我的闭卷回顾。
不要替我重写整份笔记，也不要继续追问。

今日回顾：
- 与本次相关的已有知识：{record.recall_last_learned or "未填写"}
- 核心概念：{record.recall_core_concepts or "未填写"}
- 我能讲清楚的部分：{record.recall_clear_parts or "未填写"}

展示内容按以下结构组织：
1. 回忆准确的部分
2. 明显遗漏或混淆的部分
3. 需要回看材料核对的关键点
4. 一条简短的后续学习建议

{MARKDOWN_MATH_RULES}
{STRUCTURED_RESULT_RULES}
"""


def reconstruction_review_prompt(record: DailyRecord, previous_records: list[DailyRecord]) -> str:
    del previous_records
    return f"""你是一名严谨的主动学习评阅助手。请检查我对当前内容的主动重构。
不要替我直接生成完整笔记，也不要继续追问。

今日主动重构：
- 这部分解决什么问题：{record.reconstruct_problem or "未填写"}
- 主要学了什么：{record.reconstruct_main_learning or "未填写"}
- 数学定义或推导：{record.reconstruct_math or "未填写"}

展示内容按以下结构组织：
1. 逻辑完整且表达清楚的部分
2. 概念、条件或推导上的缺口
3. 可能存在的错误或模糊表述
4. 如何进一步讲清楚

{MARKDOWN_MATH_RULES}
{STRUCTURED_RESULT_RULES}
"""


def practice_generation_prompt(record: DailyRecord, excluded_questions: list[str]) -> str:
    previous_practice = "\n".join(
        f"- {question[:500]}" for question in excluded_questions[:80] if question.strip()
    ) or "暂无"
    return f"""你是一名严谨的学习练习设计者。请生成今天必须完成的一套结构化练习。
面向学习者的题干中不得出现答案、提示或解题步骤；答案和评分标准只放入隐藏字段。

今日学习范围：{record.study_material_scope or "未填写"}
今日主要学习内容：{record.reconstruct_main_learning or "未填写"}
数学定义或推导：{record.reconstruct_math or "未填写"}
材料中已有题目、例子以及本小节历史练习题干（禁止重复）：
{previous_practice}

生成恰好 12 道题，并满足：
- 恰好 4 道选择题，占 33%；优先单选，确有必要时可以多选
- 其余 8 道覆盖概念简答、计算或应用、推导/证明/分析、综合解答和思维延伸
- 不适合证明题的学科用分析或方法比较替代，不得机械凑题型
- 难度覆盖基础、中等、挑战，且由浅入深
- 至少 70% 聚焦今日学习内容，其余用于前置知识衔接和既有薄弱点
- 不得复述、轻微改写或只替换数字/名词来复用材料中的题目、示例及历史题干
- 如果考查相同知识点，至少同时改变以下维度中的 3 项：
  任务目标、已知条件、对象/数据、表示方式、推理路径、答案形式
- 题面必须指定明确对象、条件、所需输出和必要数据；不得要求学习者
  “结合你的研究背景”“任选/自选一个现象、系统、场景或案例”后自行补题
- 开放题最多 2 道，且仍须给定具体对象与边界；优先使用可判定的概念辨析、
  条件判断、计算、推导、纠错和具体案例分析
- 应用题应直接给出一个与本节材料有关的具体情境，而不是把选择情境的责任交给学习者
- 每道题独立包含 `position`、`item_type`、`difficulty`、Markdown 题干、选项、
  隐藏答案、评分标准和实际材料定位
- 选择题选项使用稳定 ID `A`、`B`、`C`、`D`
- 非选择题的 `options` 和 `answer_key.selected_options` 返回空数组
- `source_refs` 只写实际依据，返回材料中的 `material_id`、`chunk_positions` 和简短依据摘要；
  没有直接依据时返回空数组
- `handoff` 只概括本组练习覆盖点，不得泄露答案

{MARKDOWN_MATH_RULES}
输出必须严格符合系统指定的 JSON 结构。
"""


def grading_prompt(record: DailyRecord, exercise: Exercise) -> str:
    if exercise.format_version >= 2 and exercise.items:
        item_blocks: list[str] = []
        for item in exercise.items:
            response = item.response
            local_verdict = deterministic_choice_verdict(item)
            answer_text = (
                response.answer_markdown.strip()
                if response and response.answer_markdown.strip()
                else "未填写文字答案；如有附件，请直接依据附件批改"
            )
            attachment_text = "\n\n".join(
                f"附件 {attachment.original_name}（OCR/文本提取，仅作辅助）：\n"
                f"{attachment.extracted_text or '未识别出可靠文字，请依据原图批改'}"
                for attachment in (response.attachments if response else [])
            )
            item_blocks.append(
                f"""第 {item.position} 题
题型：{item.item_type.value}
题目：{item.stem_markdown}
选项：{item.options_json}
参考答案：{item.answer_key_json}
评分标准：{item.rubric_markdown}
我的选择：{response.selected_options_json if response else "[]"}
我的作答：{answer_text}
作答附件：{attachment_text or "无"}
本地选择题判定：{local_verdict or "不适用，由你依据评分标准判断"}"""
            )
        return f"""你是一名严谨的练习批改助手。请一次批改整套 12 道题，不要继续追问。

今日学习范围：{record.study_material_scope or "未填写"}

{chr(10).join(item_blocks)}

逐题返回，不计算单题分数或整套总分：
- `position`：原题号
- `verdict`：correct / partial / incorrect
- `feedback_markdown`：
  - correct：只需明确说明“正确”，必要时补充一句关键理由
  - partial：指出缺失或不完整之处，并给出补全思路
  - incorrect：明确指出具体错误，并给出正确思路和必要步骤

选择题的“本地选择题判定”由答案键精确比对得到，`verdict` 必须与它一致；
你只负责给出简洁解释。非选择题仍由你依据参考答案和评分标准判断。

不要生成整套分数或总评，不要继续追问，也不要生成新题。
反馈必须对应用户的实际作答；正确题不要重复输出冗长标准答案。
图片附件的原图会作为多模态输入按题号紧随本提示词提供。OCR 文字只用于辅助定位，
不得因为 OCR 为空、乱码或不完整而把包含手写作答的图片判为未作答；应优先阅读原图。

{MARKDOWN_MATH_RULES}
{STRUCTURED_RESULT_RULES}
"""
    return f"""你是一名严谨的练习批改助手。请直接批改，不要继续追问。

题目：
{exercise.ai_questions}

我的答案：
{exercise.user_answers}

展示内容按以下结构组织：
1. 逐题判断：正确 / 部分正确 / 错误 / 未作答
2. 每题指出具体错误内容及错误类型
3. 给出正确思路或必要推导
4. 说明错误反映出的概念缺口或适用条件问题
5. 汇总最需要重新理解的 1-3 个要点

不要生成新的追问题目。
{MARKDOWN_MATH_RULES}
{STRUCTURED_RESULT_RULES}
"""


def preview_questions_prompt(record: DailyRecord, previous_records: list[DailyRecord]) -> str:
    del previous_records
    return f"""你是一名学习流程教练。请生成供同一课程下一次学习开场闭卷回顾的问题。
不要回答问题，不要继续追问，也不要生成超过 3 条。

今日学习范围：{record.study_material_scope or "未填写"}
今日主要学习内容：{record.reconstruct_main_learning or "未填写"}
今日数学定义或推导：{record.reconstruct_math or "未填写"}

生成恰好 3 条下次回顾问题：
- 只围绕今天已经学习的内容，不引入下一次尚未学习的新知识
- 兼顾概念连接、推导条件和应用边界
- 每条独立、具体，适合下一次学习开始时闭卷回答
- 每条只使用一个紧凑段落，不自行添加题号，不使用块级公式；短公式使用 `$...$`
- 不提供答案

{MARKDOWN_MATH_RULES}
{STRUCTURED_RESULT_RULES}
"""


def section_note_prompt(
    record: DailyRecord,
    previous_records: list[DailyRecord],
    existing_content: str = "",
    mode: str = "create",
) -> str:
    learning_records = [*previous_records, record]
    learning_context = "\n\n".join(
        f"""【{item.study_date} 主动重构】
- 问题与目标：{item.reconstruct_problem or "未填写"}
- 主要内容：{item.reconstruct_main_learning or "未填写"}
- 定义与推导：{item.reconstruct_math or "未填写"}"""
        for item in learning_records
        if any(
            value.strip()
            for value in (
                item.reconstruct_problem,
                item.reconstruct_main_learning,
                item.reconstruct_math,
            )
        )
    ) or "暂无用户主动重构内容"
    revision = ""
    if mode == "revise" and existing_content.strip():
        revision = f"""
【编辑器中已有笔记】
{existing_content}

请在已有笔记基础上补充、纠错和整理。保留其中正确且有价值的内容，不要无理由整体改写。
"""
    return f"""你是一名严谨的中文学习笔记整理者。请基于当前小节的完整学习材料、
用户已有笔记和用户自己的学习内容，生成一份详细、连贯、可长期复习的完整笔记。

【内容完整性】
1. 编辑器中已有笔记是必须保留的基础内容。除完全重复或能够确认的事实错误外，
不得删除、弱化或遗漏其中的知识点、解释、公式、例子、限定条件和用户自己的理解。
2. 必须先完整阅读本次授权的全部材料及指定范围，再开始整理。完整覆盖其中的核心
问题、概念、定义、符号、成立条件、推导过程、论证关系、例子、边界情况、注意事项和结论。
3. 完整覆盖不等于逐字照抄。应在不遗漏知识内容的前提下重新组织，使笔记能够脱离
原材料独立阅读。

【扩充与解释】
4. 补充原内容中缺失的逻辑连接、前置解释、符号含义、公式条件、推导中间步骤和必要例子。
5. 对关键内容不仅说明“是什么”和“怎么用”，还要说明它解决的根本问题、核心思想和
观察角度、与前置知识和相关概念的关系、在本章或领域中的位置，以及适用边界、局限和
容易误用之处。只有材料或可靠通用知识能够支持时，才解释方法的思想来源或提出动机，
不要为了结构完整而强行补写历史来源。
6. 必要时可以使用可靠的通用知识进行拓展。不属于原材料的内容必须明确放在
“拓展理解”等可识别部分，不得伪装成材料内容，不得虚构思想来源、历史人物或引用。

【用户历次主动重构】
{learning_context}
{revision}
【输出要求】
7. 直接输出完整中文 Markdown 笔记，不输出整理过程、覆盖清单或前言。
8. 内容应非常详细，能够用于以后独立复习；结构由知识本身决定，不强制固定标题模板。
9. 避免只罗列结论、过度碎片化和连续堆砌短句。
10. 所有公式必须保留符号定义、成立条件和必要推导。
11. 统一使用中文，必要英文术语只在首次出现时附于中文名称之后。
12. 只整理本小节学到的知识，不写学习流程、完成状态、模型评阅、练习得分、错题清单
或纠错过程；它们只可用于帮助判断哪些知识需要解释得更清楚，不应成为笔记章节。

{MARKDOWN_MATH_RULES}
{NOTE_STRUCTURED_RESULT_RULES}
"""


def course_completion_prompt(source: str) -> str:
    return f"""你是一名学习成果整理助手。请根据课程的全部章节与小节记忆，生成一份
可加入学习者长期知识背景的课程完成摘要。只使用提供的学习成果，不补充未经确认的经历。

【课程学习成果】
{source}

输出应使用简洁中文 Markdown，并包含：
- 已经掌握的知识框架
- 已经能够使用的方法或能力
- 仍然存在的边界、薄弱点或尚未覆盖的内容

不要写成课程介绍，不要夸大学习程度，总长度控制在 1200 个中文字符以内。
{MARKDOWN_MATH_RULES}
{STRUCTURED_RESULT_RULES}
"""
