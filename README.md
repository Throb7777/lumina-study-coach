<p align="center">
  <img src="docs/assets/lumina-icon.png" alt="Lumina icon" width="112">
</p>

<h1 align="center">Lumina</h1>

<p align="center">A local-first learning flow coach for deliberate, structured study.</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="https://github.com/Throb7777/lumina-study-coach/releases/tag/v0.1.3"><img alt="Latest release" src="https://img.shields.io/github/v/release/Throb7777/lumina-study-coach?include_prereleases"></a>
  <a href="https://github.com/Throb7777/lumina-study-coach/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Throb7777/lumina-study-coach/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="Apache License 2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue"></a>
  <img alt="Windows 10 and 11" src="https://img.shields.io/badge/Windows-10%20%7C%2011-5b7894">
</p>

> **Public preview:** Lumina v0.1.3 is the current public Windows release. The
> application interface is currently available in Simplified Chinese.

Lumina turns a course into chapters, sections, and focused study records. Each
study session follows a compact flow: recall, learn, reconstruct, practise,
review mistakes, and prepare the next questions. Notes are written as normal
Markdown files that remain usable in Obsidian.

<p align="center">
  <img src="docs/assets/screenshots/lumina-example.png" alt="Lumina read-only example workflow" width="1100">
</p>

## Download

Download `install_Lumina-0.1.3.exe` from the
[Lumina v0.1.3 release](https://github.com/Throb7777/lumina-study-coach/releases/tag/v0.1.3).
The installer contains the web application, local service, Python runtime, and
English and Simplified Chinese OCR support. Node.js, Python, and a separate
Tesseract installation are not required for normal use.

The preview installer is not code-signed yet, so Windows SmartScreen may ask
you to confirm before running it. Verify the SHA-256 value published with the
release before installation.

## What Lumina Does

- Organises learning as course → chapter → section.
- Creates one study record whenever you continue a section.
- Guides recall, active reconstruction, practice, correction, and next-step questions.
- Generates 12-question practice sets with one-question-at-a-time answering and review.
- Accepts compact image and PDF attachments for non-choice practice answers;
  Codex receives original images as multimodal input with local OCR as an aid,
  while PDFs use locally extracted text.
- Keeps structured mistakes, learning memory, and section notes searchable.
- Imports native-text and scanned PDFs, web pages, and supported public-video
  transcripts.
- Uses bundled English and Simplified Chinese OCR only for PDF pages that need
  it.
- Keeps text from successfully parsed PDF pages when another page fails, with
  a clear warning.
- Supports multiple priority materials at course, chapter, and section scope.
- Manages chapter and section materials in a modal without displacing the
  reading view.
- Writes final section notes to `course/chapter/section.md` inside an Obsidian vault.
- Stores courses, materials, settings, and indexes on your own computer.
- Creates and imports portable backups for moving learning data to another installation.
- Includes a read-only example course so the full workflow can be explored safely.

## AI Is Optional

Lumina does not ask for an OpenAI or Gemini API key.

- Codex-powered study tasks use a locally installed Codex CLI and its official
  ChatGPT sign-in.
- Gemini polishing uses a locally installed Antigravity CLI and its official
  Google sign-in.
- Available models depend on the connected account and provider.
- Prompts remain viewable and copyable when an external CLI is unavailable.

Course management, manual study records, materials, notes, search, and export
remain local features. See [AI connections](docs/AI_CONNECTIONS.md) for setup
and current limitations.

## Quick Start

1. Install Lumina and launch it from the desktop or Start menu.
2. Select **开始使用** in the one-time welcome dialog.
3. Open the built-in example, or create a course and its first section.
4. Add optional PDF or URL material. Scanned PDFs are handled automatically.
5. Start a study record and complete the flow.
6. Configure an Obsidian vault only when you are ready to save a section note.

Lumina listens only on `127.0.0.1`. Closing the browser does not stop a running
generation task; the local service can be stopped from Settings or the Start
menu.

## Local Data and Privacy

Installed application files and learning data are separate:

- Program files: the directory selected by the installer.
- Learning data: `%LOCALAPPDATA%\Lumina`.
- Obsidian notes: the vault selected by the user.

Lumina includes no analytics or telemetry. Network access occurs only for
features the user starts, such as downloading a URL, signing in to an external
CLI, running an AI task, or downloading the optional semantic-search model.
Bundled OCR runs locally. See [Data and privacy](docs/DATA_AND_PRIVACY.md) for
the full boundary.

Uninstalling Lumina keeps learning data by default. Choosing to delete it
requires two confirmations and creates a final backup first.

## Build from Source

Development requires Node.js 22.12+, npm 11+, Python 3.12, and uv 0.11+.

```powershell
cd frontend
npm ci
npm run check

cd ../backend
uv sync --locked
uv run ruff check .
uv run pytest
uv run alembic upgrade head
uv run alembic check
```

Use `build-installer.cmd` on Windows with Inno Setup 6 installed to create the
self-contained installer. Detailed instructions are in
[Development and builds](docs/DEVELOPMENT.md).

## Project Status

Lumina v0.1.3 is a local, single-user Windows application. It does not provide
cloud sync, multi-user collaboration, mobile-specific UI, automatic web-chat
control, or full-vault Obsidian indexing. External AI features remain subject
to the installed CLIs, account permissions, and provider availability.

## Contributing and Security

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request. Please report security issues according to
[SECURITY.md](SECURITY.md), not in a public issue.

## License

Lumina source code is licensed under the [Apache License 2.0](LICENSE).
The built-in MIT OpenCourseWare example is distributed separately under
CC BY-NC-SA 4.0. Dependencies and bundled assets retain their own licenses;
see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
