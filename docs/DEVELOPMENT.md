# Development and Builds

## Requirements

- Windows 10 or 11 for the packaged application.
- Node.js 22.12 or newer and npm 11 or newer.
- Python 3.12.
- uv 0.11 or newer.
- Inno Setup 6 for the Windows installer.

## Development Servers

```powershell
cd backend
uv sync --locked
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/courses`.

## Checks

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

## Windows Installer

Run `build-installer.cmd`. The build reads the release number from `VERSION`,
builds the frontend, creates the PyInstaller bundle, and compiles the Inno Setup
installer. Outputs are written under the ignored `output/` directory.

The generated release manifest contains relative artifact names, sizes, hashes,
the source commit, and build time. It does not contain a local absolute path.

After committing the release source and building the production installer, run
`scripts\prepare-release.ps1`. It verifies the source archive and generates the
SBOM plus `SHA256SUMS.txt` under `output\release`.
