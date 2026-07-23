from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_match(path: Path, pattern: str, label: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        raise RuntimeError(f"Could not read {label} from {path.relative_to(ROOT)}")
    return match.group(1)


def main() -> None:
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    versions = {
        "VERSION": expected,
        "frontend/package.json": json.loads(
            (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
        )["version"],
        "backend/pyproject.toml": tomllib.loads(
            (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["version"],
        "backend/app/config.py": read_match(
            ROOT / "backend" / "app" / "config.py",
            r'app_version:\s*str\s*=\s*"([^"]+)"',
            "application version",
        ),
        "installer/Lumina.iss": read_match(
            ROOT / "installer" / "Lumina.iss",
            r'#define MyAppVersion "([^"]+)"',
            "installer version",
        ),
    }
    mismatches = {name: version for name, version in versions.items() if version != expected}
    if mismatches:
        details = ", ".join(f"{name}={version}" for name, version in mismatches.items())
        raise SystemExit(f"Release version mismatch: expected {expected}; {details}")
    print(f"Release metadata is consistent: {expected}")


if __name__ == "__main__":
    main()
