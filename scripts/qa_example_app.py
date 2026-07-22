from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app import main  # noqa: E402
from app.ai_providers import AiService as BaseAiService  # noqa: E402


QA_ROOT = Path(os.environ["LUMINA_QA_DIR"]).resolve()
TODAY_FILE = QA_ROOT / "today.txt"


class IsolatedAiService(BaseAiService):
    def __init__(self, codex_home: Path, _workspace: Path) -> None:
        super().__init__(codex_home, QA_ROOT / "ai-workspace")


def qa_today() -> date:
    return date.fromisoformat(TODAY_FILE.read_text(encoding="utf-8").strip())


main.AiService = IsolatedAiService
app = main.create_app(
    static_dir=PROJECT_ROOT / "frontend" / "dist",
    database_url=f"sqlite+pysqlite:///{(QA_ROOT / 'qa.db').as_posix()}",
    material_dir=QA_ROOT / "materials",
    today_provider=qa_today,
    first_run_marker=QA_ROOT / "first-run.pending",
)
