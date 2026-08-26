import re
from dataclasses import dataclass

OUTER_MARKDOWN_FENCE = re.compile(
    r"\A\s*```(?:markdown|md)?\s*\n(?P<body>[\s\S]*?)\n```\s*\Z",
    re.IGNORECASE,
)
FENCE_LINE = re.compile(r"^\s*(`{3,}|~{3,})")
LIST_DISPLAY_START = re.compile(r"^(?P<indent>\s*)(?P<marker>(?:[-+*]|\d+[.)]))\s+\\\[\s*$")
INLINE_DISPLAY_MATH = re.compile(r"\\\[(?P<body>[^\n]+?)\\\]")
BROKEN_LATEX_ESCAPES = (
    (re.compile(r"\x7f(?=\\)"), ""),
    (re.compile(r"\x07omega\b"), "\\omega"),
    (re.compile(r"\x07(?=(?:cdots|dots)\b)"), "\\"),
    (re.compile(r"\x07(?=(?:lpha|ngle|pprox|st)\b)"), "\\a"),
    (re.compile(r"\x08(?=(?:egin|inom|eta)\b)"), "\\b"),
    (re.compile(r"\x0c(?=rac\b)"), "\\f"),
    (re.compile(r"\x0b(?=(?:dots|ec)\b)"), "\\v"),
    (re.compile(r"\t(?=(?:imes|ext|heta)(?![A-Za-z]))"), "\\t"),
    (re.compile(r"\r(?=(?:ight|ho)\b)"), "\\r"),
)
FORBIDDEN_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HTML_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
LATEX_BEGIN = re.compile(r"\\begin\{([^}]+)\}")
LATEX_END = re.compile(r"\\end\{([^}]+)\}")


@dataclass(frozen=True)
class MarkdownIssue:
    code: str
    message: str
    line: int | None = None


def normalize_ai_markdown(content: str) -> str:
    """Normalize AI Markdown to the math delimiters supported by Obsidian."""
    for pattern, replacement in BROKEN_LATEX_ESCAPES:
        content = pattern.sub(lambda _, value=replacement: value, content)
    outer_match = OUTER_MARKDOWN_FENCE.match(content)
    if outer_match:
        content = outer_match.group("body")

    lines = content.splitlines()
    normalized: list[str] = []
    active_fence: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        fence_match = FENCE_LINE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            active_fence = None if active_fence == marker else marker
            normalized.append(line)
            index += 1
            continue
        if active_fence is not None:
            normalized.append(line)
            index += 1
            continue

        line = HTML_BREAK.sub("  \n", line)

        list_display_match = LIST_DISPLAY_START.match(line)
        if list_display_match:
            closing_index = index + 1
            while closing_index < len(lines) and lines[closing_index].strip() != r"\]":
                closing_index += 1
            if closing_index < len(lines):
                body = " ".join(
                    part.strip() for part in lines[index + 1 : closing_index] if part.strip()
                )
                prefix = f"{list_display_match.group('indent')}{list_display_match.group('marker')}"
                normalized.append(f"{prefix} ${body}$")
                index = closing_index + 1
                continue

        stripped = line.strip()
        if stripped in {r"\[", r"\]"}:
            indentation = line[: len(line) - len(line.lstrip())]
            normalized.append(f"{indentation}$$")
            index += 1
            continue
        line = INLINE_DISPLAY_MATH.sub(lambda match: f"${match.group('body')}$", line)
        normalized.append(line.replace(r"\(", "$").replace(r"\)", "$"))
        index += 1

    result = "\n".join(normalized).strip()
    if match := FORBIDDEN_CONTROL.search(result):
        raise ValueError(
            f"AI Markdown 包含无法识别的控制字符 U+{ord(match.group()):04X}"
        )
    return result


def validate_note_markdown(content: str) -> tuple[str, list[MarkdownIssue]]:
    issues: list[MarkdownIssue] = []
    try:
        normalized = normalize_ai_markdown(content)
    except ValueError:
        normalized = normalize_ai_markdown(FORBIDDEN_CONTROL.sub("", content))
        issues.append(
            MarkdownIssue("forbidden_control", "内容包含无法识别的控制字符，已在预览中移除")
        )
    active_fence: tuple[str, int] | None = None
    for line_number, line in enumerate(normalized.splitlines(), start=1):
        fence_match = FENCE_LINE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if active_fence is None:
                active_fence = (marker, line_number)
            elif active_fence[0] == marker:
                active_fence = None
    if active_fence is not None:
        issues.append(
            MarkdownIssue("unclosed_fence", "代码块没有闭合", active_fence[1])
        )

    if normalized.count("$$") % 2:
        issues.append(MarkdownIssue("unmatched_display_math", "块级公式标记没有成对出现"))

    inline_source = normalized.replace("$$", "")
    inline_markers = re.findall(r"(?<!\\)\$", inline_source)
    if len(inline_markers) % 2:
        issues.append(MarkdownIssue("unmatched_inline_math", "行内公式标记没有成对出现"))

    begin_counts: dict[str, int] = {}
    end_counts: dict[str, int] = {}
    for environment in LATEX_BEGIN.findall(normalized):
        begin_counts[environment] = begin_counts.get(environment, 0) + 1
    for environment in LATEX_END.findall(normalized):
        end_counts[environment] = end_counts.get(environment, 0) + 1
    for environment in sorted(set(begin_counts) | set(end_counts)):
        if begin_counts.get(environment, 0) != end_counts.get(environment, 0):
            issues.append(
                MarkdownIssue(
                    "unmatched_latex_environment",
                    f"LaTeX 环境 {environment} 的开始和结束数量不一致",
                )
            )
    return normalized, issues
