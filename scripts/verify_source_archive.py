from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import PurePosixPath


REQUIRED = {
    "README.md",
    "README.zh-CN.md",
    "LICENSE",
    "NOTICE",
    "VERSION",
    "frontend/package-lock.json",
    "backend/uv.lock",
    "installer/Lumina.iss",
}
FORBIDDEN_PARTS = {
    ".git",
    ".agents",
    ".codex",
    ".private-docs",
    ".venv",
    "node_modules",
    "runtime-data",
    "output",
    "__pycache__",
}
FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".pid",
    ".exe",
}
SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a Lumina source ZIP.")
    parser.add_argument("archive")
    args = parser.parse_args()

    bad_entries: list[str] = []
    found: set[str] = set()
    with zipfile.ZipFile(args.archive) as archive:
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            normalized = path.as_posix().lstrip("./")
            if not normalized or normalized.endswith("/"):
                continue
            found.add(normalized)
            if path.is_absolute() or ".." in path.parts:
                bad_entries.append(f"unsafe path: {normalized}")
                continue
            if FORBIDDEN_PARTS.intersection(path.parts):
                bad_entries.append(f"forbidden directory: {normalized}")
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                bad_entries.append(f"forbidden file type: {normalized}")
            if info.file_size <= 5_000_000:
                content = archive.read(info)
                for pattern in SECRET_PATTERNS:
                    if pattern.search(content):
                        bad_entries.append(f"sensitive content: {normalized}")
                        break

    missing = sorted(REQUIRED - found)
    if missing or bad_entries:
        if missing:
            print(f"Missing required files: {missing}")
        if bad_entries:
            print("Rejected entries:")
            for entry in bad_entries:
                print(f"- {entry}")
        raise SystemExit(1)
    print(f"Source archive verified: missing_required=0, bad_entries=0, files={len(found)}")


if __name__ == "__main__":
    main()
