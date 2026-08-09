import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import update

from app.ai_providers import AiService
from app.api import cleanup_backup_runtime
from app.api import router as api_router
from app.config import settings
from app.database import create_database_engine, create_session_factory
from app.migrations import upgrade_database
from app.models import AiRun, AiRunStatus
from app.request_security import local_write_rejection
from app.static_assets import inspect_frontend_build


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    frontend_build_id: str | None
    frontend_entry: str | None
    frontend_ready: bool


class ShutdownRequest(BaseModel):
    confirm: bool


class ShutdownResponse(BaseModel):
    status: str


def create_app(
    static_dir: Path | None = None,
    database_url: str | None = None,
    material_dir: Path | None = None,
    answer_attachment_dir: Path | None = None,
    runtime_data_dir: Path | None = None,
    today_provider: Callable[[], date] | None = None,
    shutdown_callback: Callable[[], None] | None = None,
    first_run_marker: Path | None = None,
) -> FastAPI:
    resolved_database_url = database_url or settings.database_url
    resolved_material_dir = (material_dir or settings.material_dir).resolve()
    resolved_answer_attachment_dir = (
        answer_attachment_dir or settings.answer_attachment_dir
    ).resolve()
    resolved_runtime_data_dir = (runtime_data_dir or settings.runtime_data_dir).resolve()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        upgrade_database(resolved_database_url)
        engine = create_database_engine(resolved_database_url)
        application.state.session_factory = create_session_factory(engine)
        with application.state.session_factory() as session:
            session.execute(
                update(AiRun)
                .where(AiRun.status == AiRunStatus.RUNNING)
                .values(
                    status=AiRunStatus.FAILED,
                    error_text="服务已重新启动，原生成任务已中断，请重新生成。",
                )
            )
            session.commit()
        application.state.ai_service = AiService(settings.codex_home, settings.ai_workspace)
        application.state.background_tasks = set()
        application.state.material_dir = resolved_material_dir
        application.state.answer_attachment_dir = resolved_answer_attachment_dir
        application.state.runtime_data_dir = resolved_runtime_data_dir
        cleanup_backup_runtime(resolved_runtime_data_dir)
        try:
            yield
        finally:
            tasks = list(application.state.background_tasks)
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            with application.state.session_factory() as session:
                session.execute(
                    update(AiRun)
                    .where(AiRun.status == AiRunStatus.RUNNING)
                    .values(
                        status=AiRunStatus.FAILED,
                        error_text="服务已重新启动，原生成任务已中断，请重新生成。",
                    )
                )
                session.commit()
            await application.state.ai_service.close()
            engine.dispose()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    application.state.today_provider = today_provider or date.today
    application.state.shutdown_callback = shutdown_callback
    application.state.first_run_marker = (first_run_marker or settings.first_run_marker).resolve()
    resolved_static_dir = (static_dir or settings.static_dir).resolve()
    frontend_build = inspect_frontend_build(resolved_static_dir)

    @application.middleware("http")
    async def protect_local_writes(request: Request, call_next):
        rejection = local_write_rejection(request)
        if rejection:
            return JSONResponse(status_code=403, content={"detail": rejection})
        return await call_next(request)

    @application.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=settings.app_name,
            version=settings.app_version,
            frontend_build_id=frontend_build.build_id if frontend_build else None,
            frontend_entry=frontend_build.entry if frontend_build else None,
            frontend_ready=frontend_build.ready if frontend_build else False,
        )

    @application.post("/api/system/shutdown", response_model=ShutdownResponse)
    async def shutdown(payload: ShutdownRequest, request: Request) -> ShutdownResponse:
        callback = request.app.state.shutdown_callback
        if callback is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前服务不是由桌面启动器运行，请在启动终端中停止服务。",
            )
        if not payload.confirm:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="需要明确确认后才能关闭本地服务。",
            )

        asyncio.get_running_loop().call_later(0.25, callback)
        return ShutdownResponse(status="stopping")

    application.include_router(api_router)

    index_file = resolved_static_dir / "index.html"

    if index_file.is_file():

        @application.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")

            requested_file = (resolved_static_dir / full_path).resolve()
            if requested_file.is_relative_to(resolved_static_dir) and requested_file.is_file():
                headers = (
                    {"Cache-Control": "no-store"}
                    if requested_file == index_file
                    else (
                        {"Cache-Control": "public, max-age=31536000, immutable"}
                        if full_path.startswith("assets/")
                        else {"Cache-Control": "no-cache"}
                    )
                )
                return FileResponse(requested_file, headers=headers)

            if full_path == "assets" or full_path.startswith("assets/") or Path(full_path).suffix:
                raise HTTPException(status_code=404, detail="Not Found")

            return FileResponse(index_file, headers={"Cache-Control": "no-store"})
    else:

        @application.get("/", include_in_schema=False)
        async def api_root() -> dict[str, str]:
            return {"status": "api-only"}

    return application


app = create_app()
