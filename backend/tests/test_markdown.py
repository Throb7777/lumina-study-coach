from app.markdown import (
    normalize_ai_markdown,
    normalize_generated_markdown,
    validate_note_markdown,
)


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
