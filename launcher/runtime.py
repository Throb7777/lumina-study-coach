from __future__ import annotations

import ctypes
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import winreg
from dataclasses import dataclass
from pathlib import Path

SERVICE_NAME = "learning-flow-coach-api"
APPLICATION_NAME = "Lumina"
HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"
HEALTH_URL = f"{BASE_URL}/api/health"


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    backend_dir: Path
    pythonw: Path
    frontend_index: Path
    log_file: Path


def runtime_paths(project_root: Path | None = None) -> RuntimePaths:
    root = (project_root or Path(__file__).resolve().parents[1]).resolve()
    return RuntimePaths(
        project_root=root,
        backend_dir=root / "backend",
        pythonw=root / "backend" / ".venv" / "Scripts" / "pythonw.exe",
        frontend_index=root / "frontend" / "dist" / "index.html",
        log_file=root / "runtime-data" / "logs" / "server.log",
    )


def show_message(title: str, message: str, flags: int = 0x40) -> int:
    if sys.platform != "win32":
        print(f"{title}: {message}", file=sys.stderr)
        return 1
    return ctypes.windll.user32.MessageBoxW(None, message, title, flags)


def health_matches(payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and payload.get("service") == SERVICE_NAME
    )


def service_is_ready(timeout: float = 0.8) -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            return health_matches(json.loads(response.read().decode("utf-8")))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def port_is_in_use() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.4):
            return True
    except OSError:
        return False


def reload_user_proxy_environment(environment: dict[str, str]) -> None:
    names = ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")
    for name in names:
        environment.pop(name, None)
        environment.pop(name.lower(), None)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            for name in names:
                try:
                    value, _ = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    continue
                if isinstance(value, str) and value.strip():
                    environment[name] = os.path.expandvars(value.strip())
    except OSError:
        return


class SingleInstanceMutex:
    def __init__(self, project_root: Path) -> None:
        digest = hashlib.sha256(str(project_root).encode("utf-8")).hexdigest()[:16]
        self.name = f"Local\\LearningFlowCoachLauncher-{digest}"
        self.handle: int | None = None
        self.already_exists = False

    def __enter__(self) -> SingleInstanceMutex:
        if sys.platform != "win32":
            return self
        self.handle = ctypes.windll.kernel32.CreateMutexW(None, False, self.name)
        self.already_exists = ctypes.windll.kernel32.GetLastError() == 183
        return self

    def __exit__(self, *_: object) -> None:
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)


def open_application(paths: RuntimePaths) -> None:
    os.startfile(f"{BASE_URL}/courses")


def wait_until_ready(process: subprocess.Popen[bytes] | None, timeout: float = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if service_is_ready():
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(0.25)
    return False


def start_service(paths: RuntimePaths) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    reload_user_proxy_environment(environment)
    environment["STUDY_WEB_DESKTOP_LAUNCH"] = "1"
    creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    return subprocess.Popen(
        [str(paths.pythonw), "-m", "app.desktop_server"],
        cwd=paths.backend_dir,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creation_flags,
    )


def launch() -> int:
    paths = runtime_paths()
    if not paths.pythonw.is_file():
        show_message(
            APPLICATION_NAME,
            "后端运行环境尚未安装。请先双击项目目录中的 install-local.cmd。",
            0x10,
        )
        return 1
    if not paths.frontend_index.is_file():
        show_message(
            APPLICATION_NAME,
            "前端尚未构建。请先双击项目目录中的 install-local.cmd。",
            0x10,
        )
        return 1

    with SingleInstanceMutex(paths.project_root) as mutex:
        if service_is_ready():
            open_application(paths)
            return 0
        if mutex.already_exists:
            if wait_until_ready(None):
                open_application(paths)
                return 0
            show_message(APPLICATION_NAME, "本地服务仍在启动，请稍后再次打开。", 0x30)
            return 1
        if port_is_in_use():
            show_message(
                APPLICATION_NAME,
                "127.0.0.1:8000 已被其他程序占用，未启动本应用。请关闭占用程序后重试。",
                0x10,
            )
            return 1

        try:
            process = start_service(paths)
        except OSError as error:
            show_message(APPLICATION_NAME, f"无法启动本地服务：{error}", 0x10)
            return 1
        if wait_until_ready(process):
            open_application(paths)
            return 0

    show_message(
        APPLICATION_NAME,
        f"本地服务启动失败。请查看日志：\n{paths.log_file}",
        0x10,
    )
    return 1


def request_shutdown() -> bool:
    request = urllib.request.Request(
        f"{BASE_URL}/api/system/shutdown",
        data=b'{"confirm":true}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status == 200 and payload.get("status") == "stopping"
    except (OSError, ValueError, urllib.error.URLError):
        return False
