# Contributing to Lumina

Thank you for helping improve Lumina.

## Before Opening a Change

1. Search existing issues and keep the proposed change focused.
2. Do not include personal learning data, materials, databases, model output,
   credentials, absolute local paths, or Obsidian vault content.
3. Preserve the local-first course → chapter → section → study-record model.
4. Keep external AI integrations optional and explicit.

## Development Setup

Use Node.js 22.12+, npm 11+, Python 3.12, and uv 0.11+.

```powershell
cd frontend
npm ci

cd ../backend
uv sync --locked
```

Before submitting:

```powershell
cd frontend
npm run check

cd ../backend
uv run ruff check .
uv run pytest
uv run alembic upgrade head
uv run alembic check

cd ..
uv run --project backend ruff check launcher scripts
uv run --project backend python scripts/check_release_metadata.py
```

Changes to database models require an Alembic migration and upgrade/downgrade
coverage. User-facing layout changes should be checked at desktop and narrow
viewports.

## Pull Requests

Explain the problem, the chosen behavior, and the verification performed.
Avoid unrelated refactors. New dependencies need a clear reason and compatible
licensing.

By contributing, you agree that your contribution is licensed under the
Apache License 2.0.
