from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def shutdown_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/runtime/shutdown"


def wait_for_health(process: subprocess.Popen[bytes], port: int, timeout: float) -> float:
    started_at = time.monotonic()
    deadline = started_at + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Lumina exited before becoming ready ({process.returncode}).")
        try:
            with urllib.request.urlopen(health_url(port), timeout=1) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and payload.get("status") == "ok":
                    return time.monotonic() - started_at
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(0.25)
    raise TimeoutError(f"Lumina did not become ready within {timeout:.0f} seconds.")


def request_shutdown(port: int) -> None:
    request = urllib.request.Request(
        shutdown_url(port),
        data=b'{"confirm":true}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2):
            return
    except (OSError, urllib.error.URLError):
        return


def stop_process(process: subprocess.Popen[bytes], port: int) -> None:
    request_shutdown(port)
    try:
        process.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def run(executable: Path, port: int, timeout: float, log_dir: Path) -> int:
    executable = executable.resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "serve.stdout.log"
    stderr_path = log_dir / "serve.stderr.log"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            [str(executable), "--serve"],
            cwd=executable.parent,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
        )
        try:
            ready_after = wait_for_health(process, port, timeout)
            print(f"health=ok ready_after={ready_after:.2f}s pid={process.pid}")
            return 0
        finally:
            stop_process(process, port)
            print(f"stopped={process.poll() is not None}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--log-dir", type=Path, required=True)
    return parser


if __name__ == "__main__":
    arguments = build_parser().parse_args()
    raise SystemExit(
        run(
            arguments.executable,
            arguments.port,
            arguments.timeout,
            arguments.log_dir,
        )
    )
