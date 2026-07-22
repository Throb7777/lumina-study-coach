import json
import logging
import os
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

import uvicorn

from app.config import PROJECT_ROOT, settings
from app.main import create_app


def configure_logging() -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        settings.log_dir / "server.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def write_pid_file() -> None:
    settings.runtime_data_dir.mkdir(parents=True, exist_ok=True)
    settings.service_pid_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "project_root": str(PROJECT_ROOT),
                "host": settings.host,
                "port": settings.port,
                "started_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def remove_pid_file() -> None:
    try:
        payload = json.loads(settings.service_pid_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return
    if payload.get("pid") == os.getpid():
        settings.service_pid_path.unlink(missing_ok=True)


def run() -> None:
    configure_logging()
    server_ref: dict[str, uvicorn.Server] = {}

    def request_shutdown() -> None:
        server = server_ref.get("server")
        if server is not None:
            server.should_exit = True

    application = create_app(shutdown_callback=request_shutdown)
    config = uvicorn.Config(
        application,
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=True,
    )
    server = uvicorn.Server(config)
    server_ref["server"] = server
    write_pid_file()
    logging.getLogger(__name__).info(
        "Starting Lumina on http://%s:%s", settings.host, settings.port
    )
    try:
        server.run()
    finally:
        remove_pid_file()
        logging.getLogger(__name__).info("Lumina stopped")


if __name__ == "__main__":
    run()
