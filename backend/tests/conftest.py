from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    database_path = (tmp_path / "test.db").as_posix()
    return f"sqlite+pysqlite:///{database_path}"


@pytest.fixture
def app(tmp_path: Path, database_url: str) -> FastAPI:
    return create_app(
        static_dir=tmp_path / "missing-dist",
        database_url=database_url,
        material_dir=tmp_path / "materials",
        answer_attachment_dir=tmp_path / "answer-attachments",
        runtime_data_dir=tmp_path / "runtime-data",
        first_run_marker=tmp_path / "first-run.pending",
    )


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
