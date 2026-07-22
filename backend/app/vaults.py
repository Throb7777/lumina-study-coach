import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class VaultBrowserUnavailableError(RuntimeError):
    pass


class VaultBrowserError(RuntimeError):
    pass


@dataclass(frozen=True)
class VaultCandidate:
    name: str
    path: str
    has_obsidian_directory: bool
    writable: bool


def inspect_vault(path: str | Path) -> VaultCandidate:
    resolved = Path(path).expanduser().resolve()
    return VaultCandidate(
        name=resolved.name or str(resolved),
        path=str(resolved),
        has_obsidian_directory=(resolved / ".obsidian").is_dir(),
        writable=resolved.is_dir() and os.access(resolved, os.W_OK),
    )


def obsidian_config_paths() -> list[Path]:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        return [Path(appdata) / "obsidian" / "obsidian.json"] if appdata else []
    if sys.platform == "darwin":
        return [Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"]
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return [config_home / "obsidian" / "obsidian.json"]


def discover_obsidian_vaults() -> list[VaultCandidate]:
    candidates: list[VaultCandidate] = []
    seen_paths: set[str] = set()
    for config_path in obsidian_config_paths():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        vaults = data.get("vaults", {})
        if not isinstance(vaults, dict):
            continue
        for entry in vaults.values():
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                continue
            path = Path(entry["path"]).expanduser()
            if not path.is_dir():
                continue
            candidate = inspect_vault(path)
            path_key = os.path.normcase(candidate.path)
            if path_key not in seen_paths:
                seen_paths.add(path_key)
                candidates.append(candidate)
    return sorted(candidates, key=lambda candidate: candidate.name.casefold())


def vault_browser_supported() -> bool:
    return sys.platform == "win32" and shutil.which("powershell.exe") is not None


def browse_for_vault() -> VaultCandidate | None:
    if not vault_browser_supported():
        raise VaultBrowserUnavailableError("当前系统暂不支持原生目录选择，请手动输入路径")

    script = """
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '选择 Obsidian Vault'
$dialog.ShowNewFolderButton = $false
$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::Write($dialog.SelectedPath)
}
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise VaultBrowserError("无法打开目录选择窗口") from error

    if result.returncode != 0:
        raise VaultBrowserError("目录选择窗口运行失败")
    selected_path = result.stdout.strip()
    return inspect_vault(selected_path) if selected_path else None
