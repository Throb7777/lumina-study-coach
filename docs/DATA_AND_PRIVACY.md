# Data and Privacy

Lumina is local-first and does not include analytics, advertising, or telemetry.

## Stored Locally

The installed application stores its data under `%LOCALAPPDATA%\Lumina`:

- SQLite learning database.
- Uploaded PDFs, downloaded pages, and transcript snapshots.
- OCR cache and local full-text/semantic indexes.
- Application settings, logs, backups, and process state.

Obsidian notes are written only inside the vault selected by the user. Lumina
manages only course folders and note files that it creates.

## Network Access

Network access occurs only for an explicit feature:

- Downloading or refreshing a URL or supported transcript.
- Signing in to Codex or Antigravity.
- Running an external AI task.
- Downloading the optional semantic-search model.

The Windows installer includes the OCR engine and its English and Simplified
Chinese language data. PDF OCR runs locally and does not download a model or
send the document to an OCR service.

Reference material is treated as untrusted content. Lumina does not expose its
local service beyond `127.0.0.1`.

## Logs and Backups

Logs do not intentionally record study text, prompts, full material content, or
model responses. Backups include the learning database and original local
materials, but exclude logs, model login state, generated indexes, caches, and
the Obsidian vault.

Uninstall keeps data by default. A full data removal requires two confirmations
and a successful final backup.
