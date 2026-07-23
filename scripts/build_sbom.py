from __future__ import annotations

import argparse
import json
import tomllib
import uuid
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = uuid.UUID("dca620c0-9adb-5a34-b2e7-18c9e2dc5238")


def npm_components() -> list[dict[str, str]]:
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    components = []
    for path, package in lock.get("packages", {}).items():
        if not path.startswith("node_modules/"):
            continue
        name = package.get("name") or path.removeprefix("node_modules/")
        version = package.get("version")
        if not version:
            continue
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:npm/{quote(name, safe='@/')}@{quote(version)}",
            }
        )
    return components


def python_components() -> list[dict[str, str]]:
    lock = tomllib.loads((ROOT / "backend" / "uv.lock").read_text(encoding="utf-8"))
    components = []
    for package in lock.get("package", []):
        name = package.get("name")
        version = package.get("version")
        if not name or not version or package.get("source", {}).get("editable"):
            continue
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{quote(name)}@{quote(version)}",
            }
        )
    return components


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a CycloneDX dependency inventory.")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    unique = {
        (component["purl"], component["version"]): component
        for component in npm_components() + python_components()
    }
    components = sorted(unique.values(), key=lambda item: (item["name"].lower(), item["version"]))
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid5(NAMESPACE, f'lumina-{version}')}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "lumina-study-coach",
                "version": version,
                "licenses": [{"license": {"id": "Apache-2.0"}}],
            }
        },
        "components": components,
    }
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(
        json.dumps(bom, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(components)} components to {args.destination}")


if __name__ == "__main__":
    main()
