from __future__ import annotations

import argparse
import ctypes
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

APPLICATION_NAME = "Lumina"
SERVICE_NAME = "learning-flow-coach-api"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def bundle_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root).resolve() if frozen_root else source_root()


def release_data_root(environment: dict[str, str] | None = None) -> Path:
    values = environment if environment is not None else os.environ
    override = values.get("LUMINA_DATA_DIR", "").strip()
    if override:
        return Path(os.path.expandvars(override)).expanduser().resolve()
    local_app_data = values.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return (Path(local_app_data).expanduser() / "Lumina").resolve()
    return (Path.home() / ".local" / "share" / "Lumina").resolve()


def apply_install_config(
    environment: dict[str, str],
    executable: Path | None = None,
) -> None:
    config_path = (executable or Path(sys.executable)).resolve().parent / "install-config.json"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return
    data_dir = payload.get("data_dir")
    port = payload.get("port")
    if "LUMINA_DATA_DIR" not in environment and isinstance(data_dir, str) and data_dir.strip():
        environment["LUMINA_DATA_DIR"] = data_dir.strip()
    if "LEARNING_COACH_PORT" not in environment and isinstance(port, int):
        environment["LEARNING_COACH_PORT"] = str(port)


def release_port(environment: dict[str, str] | None = None) -> int:
    values = environment if environment is not None else os.environ
    raw_port = values.get("LEARNING_COACH_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw_port)
    except ValueError:
        return DEFAULT_PORT
    return port if 1 <= port <= 65535 else DEFAULT_PORT


@dataclass(frozen=True)
class ReleasePaths:
    executable: Path
    bundled: Path
    static_dir: Path
    data_root: Path
    database: Path
    materials: Path
    ai_runtime: Path
    log_file: Path
    first_run_marker: Path


def release_paths(
    environment: dict[str, str] | None = None,
    *,
    executable: Path | None = None,
    bundled: Path | None = None,
) -> ReleasePaths:
    data_root = release_data_root(environment)
    package_root = (bundled or bundle_root()).resolve()
    executable_path = (executable or Path(sys.executable)).resolve()
    return ReleasePaths(
        executable=executable_path,
        bundled=package_root,
        static_dir=package_root / "frontend" / "dist",
        data_root=data_root,
        database=data_root / "learning-flow-coach.db",
        materials=data_root / "materials",
        ai_runtime=data_root / "ai",
        log_file=data_root / "logs" / "server.log",
        first_run_marker=data_root / "first-run.pending",
    )


def configure_release_environment(
    paths: ReleasePaths,
    environment: dict[str, str] | None = None,
) -> dict[str, str]:
    target = environment if environment is not None else os.environ
    target["LEARNING_COACH_HOST"] = DEFAULT_HOST
    target["LEARNING_COACH_PORT"] = str(release_port(target))
    target["LEARNING_COACH_STATIC_DIR"] = str(paths.static_dir)
    target["LEARNING_COACH_RUNTIME_DATA_DIR"] = str(paths.data_root)
    target["LEARNING_COACH_DATABASE_PATH"] = str(paths.database)
    target["LEARNING_COACH_AI_RUNTIME_DIR"] = str(paths.ai_runtime)
    return target


def initialize_data_root(paths: ReleasePaths) -> None:
    paths.data_root.mkdir(parents=True, exist_ok=True)
    if not paths.database.is_file() and not paths.first_run_marker.exists():
        paths.first_run_marker.write_text("pending", encoding="ascii")


def show_message(title: str, message: str, flags: int = 0x40) -> int:
    if sys.platform != "win32":
        print(f"{title}: {message}", file=sys.stderr)
        return 1
    return ctypes.windll.user32.MessageBoxW(None, message, title, flags)


def service_urls(environment: dict[str, str] | None = None) -> tuple[str, str, str]:
    base = f"http://{DEFAULT_HOST}:{release_port(environment)}"
    return base, f"{base}/api/health", f"{base}/api/system/shutdown"


def health_matches(payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and payload.get("service") == SERVICE_NAME
    )


def service_is_ready(environment: dict[str, str] | None = None, timeout: float = 0.8) -> bool:
    _, health_url, _ = service_urls(environment)
    try:
        with urllib.request.urlopen(health_url, timeout=timeout) as response:
            return health_matches(json.loads(response.read().decode("utf-8")))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def port_is_in_use(environment: dict[str, str] | None = None) -> bool:
    try:
        with socket.create_connection(
            (DEFAULT_HOST, release_port(environment)),
            timeout=0.4,
        ):
            return True
    except OSError:
        return False


def service_process_id(environment: dict[str, str] | None = None) -> int | None:
    pid_path = release_data_root(environment) / "service.pid"
    try:
        payload = json.loads(pid_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    process_id = payload.get("pid")
    if (
        not isinstance(process_id, int)
        or process_id <= 0
        or payload.get("host") != DEFAULT_HOST
        or payload.get("port") != release_port(environment)
    ):
        return None
    return process_id


def process_is_running(process_id: int) -> bool:
    if sys.platform != "win32":
        try:
            os.kill(process_id, 0)
        except OSError:
            return False
        return True
    synchronize = 0x00100000
    wait_timeout = 0x00000102
    handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, process_id)
    if not handle:
        return False
    try:
        return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == wait_timeout
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


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


class ReleaseMutex:
    name = "Local\\LuminaStudyCoachLauncher"

    def __init__(self) -> None:
        self.handle: int | None = None
        self.already_exists = False

    def __enter__(self) -> ReleaseMutex:
        if sys.platform != "win32":
            return self
        self.handle = ctypes.windll.kernel32.CreateMutexW(None, False, self.name)
        self.already_exists = ctypes.windll.kernel32.GetLastError() == 183
        return self

    def __exit__(self, *_: object) -> None:
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)


def wait_until_ready(
    process: subprocess.Popen[bytes] | None,
    environment: dict[str, str] | None = None,
    timeout: float = 30,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if service_is_ready(environment):
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(0.25)
    return False


def wait_until_stopped(
    environment: dict[str, str] | None = None,
    timeout: float = 15,
    process_id: int | None = None,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process_id is not None:
            if not process_is_running(process_id):
                return True
        elif not service_is_ready(environment, timeout=0.25) and not port_is_in_use(
            environment
        ):
            return True
        time.sleep(0.25)
    if process_id is not None:
        return not process_is_running(process_id)
    return not service_is_ready(environment, timeout=0.25) and not port_is_in_use(
        environment
    )


def start_service(paths: ReleasePaths, environment: dict[str, str]) -> subprocess.Popen[bytes]:
    child_environment = environment.copy()
    reload_user_proxy_environment(child_environment)
    child_environment["STUDY_WEB_DESKTOP_LAUNCH"] = "1"
    creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    return subprocess.Popen(
        [str(paths.executable), "--serve"],
        cwd=paths.executable.parent,
        env=child_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creation_flags,
    )


def request_shutdown(environment: dict[str, str] | None = None) -> bool:
    _, _, shutdown_url = service_urls(environment)
    request = urllib.request.Request(
        shutdown_url,
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


def open_application(environment: dict[str, str] | None = None) -> None:
    base_url, _, _ = service_urls(environment)
    os.startfile(f"{base_url}/courses")


def launch(paths: ReleasePaths, environment: dict[str, str]) -> int:
    if not paths.static_dir.joinpath("index.html").is_file():
        show_message(APPLICATION_NAME, "安装文件不完整，请重新安装 Lumina。", 0x10)
        return 1
    initialize_data_root(paths)
    with ReleaseMutex() as mutex:
        if service_is_ready(environment):
            open_application(environment)
            return 0
        if mutex.already_exists:
            if wait_until_ready(None, environment):
                open_application(environment)
                return 0
            show_message(APPLICATION_NAME, "本地服务仍在启动，请稍后再次打开。", 0x30)
            return 1
        if port_is_in_use(environment):
            show_message(
                APPLICATION_NAME,
                f"{DEFAULT_HOST}:{release_port(environment)} 已被其他程序占用。",
                0x10,
            )
            return 1
        try:
            process = start_service(paths, environment)
        except OSError as error:
            show_message(APPLICATION_NAME, f"无法启动本地服务：{error}", 0x10)
            return 1
        if wait_until_ready(process, environment):
            open_application(environment)
            return 0
    show_message(
        APPLICATION_NAME,
        f"本地服务启动失败。请查看日志：\n{paths.log_file}",
        0x10,
    )
    return 1


def run_server(paths: ReleasePaths, environment: dict[str, str]) -> int:
    initialize_data_root(paths)
    environment["STUDY_WEB_DESKTOP_LAUNCH"] = "1"
    from app.desktop_server import run

    run()
    return 0


def stop_service(environment: dict[str, str], *, silent: bool) -> int:
    process_id = service_process_id(environment)
    if not service_is_ready(environment):
        if process_id is not None and process_is_running(process_id) and not wait_until_stopped(
            environment,
            process_id=process_id,
        ):
            if not silent:
                show_message(APPLICATION_NAME, "本地服务未能完全关闭。", 0x10)
            return 1
        if not silent:
            show_message(APPLICATION_NAME, "本地服务当前没有运行。", 0x40)
        return 0
    if not silent:
        choice = show_message(
            f"关闭 {APPLICATION_NAME}",
            "确定关闭本地服务吗？正在运行的生成任务会被中断。",
            0x21,
        )
        if choice != 1:
            return 0
    request_shutdown(environment)
    if wait_until_stopped(environment, process_id=process_id):
        return 0
    if not silent:
        show_message(
            APPLICATION_NAME,
            "无法安全关闭本地服务。请稍后重试，或先结束正在运行的任务。",
            0x10,
        )
    return 1


def backup_data(paths: ReleasePaths, destination: Path) -> int:
    from launcher.data_archive import create_backup_archive

    archive = create_backup_archive(
        paths.database,
        paths.materials,
        destination.expanduser().resolve(),
    )
    if archive is not None:
        print(archive)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--initialize-install", action="store_true")
    parser.add_argument("--backup-data", type=Path)
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    apply_install_config(os.environ)
    paths = release_paths()
    environment = configure_release_environment(paths)
    if args.serve:
        return run_server(paths, environment)
    if args.stop:
        return stop_service(environment, silent=args.silent)
    if args.initialize_install:
        initialize_data_root(paths)
        return 0
    if args.backup_data is not None:
        return backup_data(paths, args.backup_data)
    return launch(paths, environment)


if __name__ == "__main__":
    raise SystemExit(main())
