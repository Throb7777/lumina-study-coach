from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LEARNING_COACH_",
        extra="ignore",
    )

    app_name: str = "learning-flow-coach-api"
    app_version: str = "0.1.1"
    host: str = "127.0.0.1"
    port: int = 8000
    static_dir: Path = PROJECT_ROOT / "frontend" / "dist"
    runtime_data_dir: Path = PROJECT_ROOT / "runtime-data"
    database_path: Path = PROJECT_ROOT / "runtime-data" / "learning-flow-coach.db"
    ai_runtime_dir: Path = PROJECT_ROOT / "runtime-data" / "ai"

    @property
    def codex_home(self) -> Path:
        return self.ai_runtime_dir / "codex-home"

    @property
    def ai_workspace(self) -> Path:
        return self.ai_runtime_dir / "workspace"

    @property
    def material_dir(self) -> Path:
        return self.runtime_data_dir / "materials"

    @property
    def log_dir(self) -> Path:
        return self.runtime_data_dir / "logs"

    @property
    def service_pid_path(self) -> Path:
        return self.runtime_data_dir / "service.pid"

    @property
    def first_run_marker(self) -> Path:
        return self.runtime_data_dir / "first-run.pending"

    @property
    def database_url(self) -> str:
        database_path = self.database_path.expanduser().resolve().as_posix()
        return f"sqlite+pysqlite:///{database_path}"


settings = Settings()
