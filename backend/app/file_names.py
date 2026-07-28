import unicodedata

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
WINDOWS_CHARACTER_REPLACEMENTS = str.maketrans(
    {
        "<": "＜",
        ">": "＞",
        ":": "：",
        '"': "＂",
        "/": "／",
        "\\": "＼",
        "|": "｜",
        "?": "？",
        "*": "＊",
    }
)


def safe_path_segment(
    value: str,
    fallback: str,
    *,
    max_length: int = 100,
    suffix: str = "",
    force_suffix: bool = False,
) -> str:
    normalized = unicodedata.normalize("NFC", value)
    one_line = " ".join(normalized.split())
    cleaned = "".join(
        " " if ord(character) < 32 else character.translate(WINDOWS_CHARACTER_REPLACEMENTS)
        for character in one_line
    )
    cleaned = " ".join(cleaned.split())
    while cleaned.endswith("."):
        cleaned = f"{cleaned[:-1]}。"
    cleaned = cleaned.rstrip(" ")

    changed = cleaned != value
    if not cleaned:
        cleaned = fallback
        changed = True
    if cleaned.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"＿{cleaned}"
        changed = True

    needs_suffix = bool(suffix) and (changed or force_suffix or len(cleaned) > max_length)
    applied_suffix = suffix if needs_suffix else ""
    available_length = max_length - len(applied_suffix)
    if available_length < 1:
        raise ValueError("文件名后缀超过允许长度")
    cleaned = cleaned[:available_length].rstrip(" .")
    if not cleaned:
        cleaned = fallback[:available_length].rstrip(" .") or "_"
    return f"{cleaned}{applied_suffix}"
