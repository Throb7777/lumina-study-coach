from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


class _ModuleEntryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.entry: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if self.entry is not None or tag != "script":
            return
        attributes = dict(attrs)
        if attributes.get("type") == "module" and attributes.get("src"):
            self.entry = attributes["src"]


@dataclass(frozen=True)
class FrontendBuildInfo:
    build_id: str
    entry: str | None
    ready: bool


def inspect_frontend_build(static_dir: Path) -> FrontendBuildInfo | None:
    index_file = static_dir / "index.html"
    try:
        index_bytes = index_file.read_bytes()
        index_text = index_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    parser = _ModuleEntryParser()
    parser.feed(index_text)
    entry = parser.entry
    entry_file: Path | None = None
    if entry:
        entry_path = urlsplit(entry).path.lstrip("/")
        candidate = (static_dir / entry_path).resolve()
        if candidate.is_relative_to(static_dir):
            entry_file = candidate

    return FrontendBuildInfo(
        build_id=sha256(index_bytes).hexdigest()[:16],
        entry=entry,
        ready=entry_file is not None and entry_file.is_file(),
    )
