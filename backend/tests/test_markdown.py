import pytest

from app.markdown import (
    normalize_ai_markdown,
    normalize_compact_generated_markdown,
    normalize_generated_markdown,
    validate_note_markdown,
)


def test_compacts_short_feedback_formulas_but_preserves_structured_math() -> None:
    source = r"""likelihood 可写为

$$
L(\theta)=\prod_{i=1}^{n}f(x_i\mid\theta)
$$

矩阵推导如下：

$$
\begin{aligned}x&=1\\y&=2\end{aligned}
$$"""

    expected = (
        r"likelihood 可写为 $L(\theta)=\prod_{i=1}^{n}f(x_i\mid\theta)$"
        "\n\n矩阵推导如下：\n\n"
        "$$\n"
        r"\begin{aligned}x&=1\\y&=2\end{aligned}"
        "\n$$"
    )

    assert normalize_compact_generated_markdown(source) == expected


@pytest.mark.parametrize("source", [
    "正文\n\n```text\n$$x=1$$\n```",
    "示例 `$$x=1$$` 不变。",
    "正文\n\n    $$x=1$$",
    "$$\nx=1\ny=2\n$$",
    "$$\n\\begin{cases}x&=1\\\\y&=2\\end{cases}\n$$",
    "$$" + "x+" * 100 + "1$$",
    "$$\nx=1",
    "可得\n\n$x=1$",
])
def test_compact_feedback_preserves_code_and_explicit_structure(source: str) -> None:
    assert normalize_compact_generated_markdown(source) == source


@pytest.mark.parametrize("prefix", ["# 定义：", "---", "独立段落。", "```", "> 引用："])
def test_compact_feedback_does_not_merge_unrelated_blocks(prefix: str) -> None:
    if prefix == "```":
        prefix = "```text\ncode\n```"
    assert normalize_compact_generated_markdown(prefix + "\n\n$$x=1$$") == (
        prefix + "\n\n$x=1$"
    )


def test_compact_feedback_is_idempotent() -> None:
    source = "- 可得\n\n$$x=1$$\n\n最大化它等价于最大化\n\n$$L=x$$"
    result = normalize_compact_generated_markdown(source)
    assert result == "- 可得 $x=1$\n\n最大化它等价于最大化 $L=x$"
    assert normalize_compact_generated_markdown(result) == result


def test_normalizes_obsidian_math_delimiters_and_outer_fence() -> None:
    source = """```markdown
# 条件概率

行内公式 \\(P(A\\mid B)\\)。

\\[
P(A\\mid B)=\\frac{P(A\\cap B)}{P(B)}
\\]
```"""

    assert (
        normalize_ai_markdown(source)
        == """# 条件概率

行内公式 $P(A\\mid B)$。

$$
P(A\\mid B)=\\frac{P(A\\cap B)}{P(B)}
$$"""
    )


def test_preserves_math_like_text_inside_code_fences() -> None:
    source = """正文 \\(x\\)

```python
value = r"\\(x\\)"
\\[
```"""

    assert (
        normalize_ai_markdown(source)
        == """正文 $x$

```python
value = r"\\(x\\)"
\\[
```"""
    )


def test_normalizes_display_math_inside_markdown_lists() -> None:
    source = r"""### 第3题

- \[
P(A)=\frac{4}{9}
\]
- \[P(B\mid A)=\frac{3}{8}\]

---

### 第4题"""

    assert (
        normalize_ai_markdown(source)
        == r"""### 第3题

- $P(A)=\frac{4}{9}$
- $P(B\mid A)=\frac{3}{8}$

---

### 第4题"""
    )


def test_repairs_bell_character_before_latex_dot_commands() -> None:
    source = "$Ax=x_1a_1+\x07cdots+x_na_n$ and $a_1,\x07dots,a_n$ and $\x07omega$"

    assert normalize_ai_markdown(source) == (
        r"$Ax=x_1a_1+\cdots+x_na_n$ and $a_1,\dots,a_n$ and $\omega$"
    )


def test_repairs_json_control_characters_inside_common_latex_commands() -> None:
    source = (
        "$\x0crac{3}{4}$ "
        "$\x08egin{bmatrix}1\\\\2\\end{bmatrix}$ "
        "$2\times3$ $\x0bdots$ $\right)$"
    )

    assert normalize_ai_markdown(source) == (
        r"$\frac{3}{4}$ $\begin{bmatrix}1\\2\end{bmatrix}$ "
        r"$2\times3$ $\vdots$ $\right)$"
    )


def test_repairs_delete_character_before_latex_commands() -> None:
    source = "$\x7f\\sigma$ 与随机变量 $X$ 使用相同单位"

    assert normalize_ai_markdown(source) == r"$\sigma$ 与随机变量 $X$ 使用相同单位"


def test_repairs_delete_character_before_latex_symbol_escapes() -> None:
    source = "$\x7f\\{X>t+s\\}$"

    assert normalize_ai_markdown(source) == r"$\{X>t+s\}$"


def test_generated_markdown_removes_unknown_json_control_characters() -> None:
    source = "$\x08E[X]=\\mu$ 且正文\x01继续"

    assert normalize_generated_markdown(source) == r"$E[X]=\mu$ 且正文继续"


def test_normalizes_html_breaks_outside_code_fences() -> None:
    source = "第一行<br>第二行\n\n```html\n<br>\n```"

    assert normalize_ai_markdown(source) == "第一行  \n第二行\n\n```html\n<br>\n```"


def test_repairs_duplicate_latex_command_escape_only_in_inline_math() -> None:
    source = r"""协方差 $\\mathrm{Cov}(X,Y)$。

$$
\\begin{aligned}x&=1\\y&=2\\end{aligned}
$$"""

    assert normalize_ai_markdown(source) == (
        r"""协方差 $\mathrm{Cov}(X,Y)$。

$$
\\begin{aligned}x&=1\\y&=2\\end{aligned}
$$"""
    )


def test_reports_unclosed_fences_and_unmatched_math_structure() -> None:
    normalized, issues = validate_note_markdown(
        "正文\n\n```python\nvalue = 1\n\n$$\n\\begin{aligned}x=1"
    )

    assert normalized
    assert {issue.code for issue in issues} == {
        "unclosed_fence",
        "unmatched_display_math",
        "unmatched_latex_environment",
    }


def test_reports_and_removes_unknown_control_characters_during_validation() -> None:
    normalized, issues = validate_note_markdown("正文\x01内容")

    assert normalized == "正文内容"
    assert [issue.code for issue in issues] == ["forbidden_control"]
