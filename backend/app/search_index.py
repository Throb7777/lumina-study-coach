from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from sqlalchemy.orm import Session

from app.models import AppSetting

SEMANTIC_SEARCH_SETTING = "semantic_search_enabled"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_MODEL_SIZE = "约 220 MB"
EMBEDDING_MODEL_FILE = "model_optimized.onnx"
INDEX_VERSION = "hybrid-v1"


class EmbeddingModel(Protocol):
    def embed(self, documents: list[str]): ...

    def query_embed(self, query: str): ...


@dataclass(frozen=True)
class SearchDocument:
    key: str
    content: str


_embedding_models: dict[Path, EmbeddingModel] = {}


def index_path(session: Session) -> Path:
    database = session.get_bind().url.database
    if not database:
        raise RuntimeError("混合检索只支持本地 SQLite 数据库")
    return Path(database).resolve().parent / "search-index.db"


def model_cache_path(session: Session) -> Path:
    return index_path(session).parent / "search-models"


def semantic_enabled(session: Session) -> bool:
    setting = session.get(AppSetting, SEMANTIC_SEARCH_SETTING)
    return setting is not None and setting.value == "1"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS indexed_chunks ("
        "chunk_key TEXT PRIMARY KEY, content TEXT NOT NULL, vector BLOB, vector_model TEXT)"
    )
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5("
            "chunk_key UNINDEXED, content, tokenize='trigram')"
        )
    except sqlite3.OperationalError:
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5("
            "chunk_key UNINDEXED, content)"
        )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    return connection


def _model(cache_path: Path) -> EmbeddingModel:
    resolved = cache_path.resolve()
    cached = _embedding_models.get(resolved)
    if cached is not None:
        return cached
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=EMBEDDING_MODEL, cache_dir=str(resolved))
    _embedding_models[resolved] = model
    return model


def prepare_semantic_model_paths(index: Path, cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    _model(cache)
    with _connect(index) as connection:
        connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('model_ready', ?)",
            (EMBEDDING_MODEL,),
        )
        connection.commit()


def prepare_semantic_model(session: Session) -> None:
    prepare_semantic_model_paths(index_path(session), model_cache_path(session))


def model_ready(session: Session) -> bool:
    path = index_path(session)
    if not path.is_file():
        return False
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT value FROM metadata WHERE key='model_ready'"
        ).fetchone()
    cache = model_cache_path(session)
    return (
        row is not None
        and row[0] == EMBEDDING_MODEL
        and any(cache.rglob(EMBEDDING_MODEL_FILE))
        and any(cache.rglob("tokenizer.json"))
    )


def set_semantic_enabled(session: Session, enabled: bool) -> None:
    setting = session.get(AppSetting, SEMANTIC_SEARCH_SETTING)
    value = "1" if enabled else "0"
    if setting is None:
        session.add(AppSetting(key=SEMANTIC_SEARCH_SETTING, value=value))
    else:
        setting.value = value
    session.commit()


def _sync_documents(connection: sqlite3.Connection, documents: list[SearchDocument]) -> None:
    existing = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT chunk_key, content FROM indexed_chunks WHERE chunk_key IN ({})".format(
                ",".join("?" for _ in documents)
            ),
            [document.key for document in documents],
        )
    } if documents else {}
    for document in documents:
        if existing.get(document.key) == document.content:
            continue
        connection.execute(
            "INSERT INTO indexed_chunks(chunk_key, content, vector, vector_model) "
            "VALUES(?, ?, NULL, NULL) ON CONFLICT(chunk_key) DO UPDATE SET "
            "content=excluded.content, vector=NULL, vector_model=NULL",
            (document.key, document.content),
        )
        connection.execute("DELETE FROM chunk_fts WHERE chunk_key=?", (document.key,))
        connection.execute(
            "INSERT INTO chunk_fts(chunk_key, content) VALUES(?, ?)",
            (document.key, document.content),
        )


def _fts_ranks(
    connection: sqlite3.Connection,
    documents: list[SearchDocument],
    query: str,
) -> dict[str, int]:
    terms = [term for term in query.replace('"', " ").split() if len(term) >= 3][:12]
    if not terms:
        compact = "".join(query.split())
        terms = [compact[:80]] if len(compact) >= 3 else []
    if not terms:
        return {}
    match_query = " OR ".join(f'"{term}"' for term in terms)
    allowed = {document.key for document in documents}
    try:
        rows = connection.execute(
            "SELECT chunk_key FROM chunk_fts WHERE chunk_fts MATCH ? "
            "ORDER BY bm25(chunk_fts) LIMIT 80",
            (match_query,),
        )
    except sqlite3.OperationalError:
        return {}
    return {key: rank for rank, (key,) in enumerate(rows, start=1) if key in allowed}


def _vector_ranks(
    connection: sqlite3.Connection,
    documents: list[SearchDocument],
    query: str,
    cache_path: Path,
) -> dict[str, int]:
    model = _model(cache_path)
    missing_rows = list(
        connection.execute(
            "SELECT chunk_key, content FROM indexed_chunks "
            "WHERE chunk_key IN ({}) AND (vector IS NULL OR vector_model != ?)".format(
                ",".join("?" for _ in documents)
            ),
            [document.key for document in documents] + [EMBEDDING_MODEL],
        )
    ) if documents else []
    if missing_rows:
        vectors = list(model.embed([row[1] for row in missing_rows]))
        for (key, _), vector in zip(missing_rows, vectors, strict=True):
            connection.execute(
                "UPDATE indexed_chunks SET vector=?, vector_model=? WHERE chunk_key=?",
                (np.asarray(vector, dtype=np.float32).tobytes(), EMBEDDING_MODEL, key),
            )
    query_vector = np.asarray(next(iter(model.query_embed(query))), dtype=np.float32)
    query_norm = float(np.linalg.norm(query_vector)) or 1.0
    scores: list[tuple[float, str]] = []
    for key, blob in connection.execute(
        "SELECT chunk_key, vector FROM indexed_chunks WHERE chunk_key IN ({})".format(
            ",".join("?" for _ in documents)
        ),
        [document.key for document in documents],
    ):
        if blob is None:
            continue
        vector = np.frombuffer(blob, dtype=np.float32)
        denominator = (float(np.linalg.norm(vector)) or 1.0) * query_norm
        scores.append((float(np.dot(vector, query_vector)) / denominator, key))
    scores.sort(reverse=True)
    return {key: rank for rank, (_, key) in enumerate(scores, start=1)}


def hybrid_rank_bonuses(
    session: Session,
    documents: list[SearchDocument],
    query: str,
) -> dict[str, float]:
    if not documents or not query.strip():
        return {}
    path = index_path(session)
    with _connect(path) as connection:
        _sync_documents(connection, documents)
        fts_ranks = _fts_ranks(connection, documents, query)
        vector_ranks: dict[str, int] = {}
        if semantic_enabled(session) and model_ready(session):
            try:
                vector_ranks = _vector_ranks(
                    connection,
                    documents,
                    query,
                    model_cache_path(session),
                )
            except Exception as error:
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES('last_vector_error', ?)",
                    (json.dumps(str(error), ensure_ascii=False),),
                )
        connection.commit()
    bonuses: dict[str, float] = {}
    for key, rank in fts_ranks.items():
        bonuses[key] = bonuses.get(key, 0.0) + 20.0 / (8 + rank)
    for key, rank in vector_ranks.items():
        bonuses[key] = bonuses.get(key, 0.0) + 28.0 / (8 + rank)
    return bonuses
