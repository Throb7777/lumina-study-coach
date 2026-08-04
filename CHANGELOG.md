# Changelog

All notable public changes to Lumina are documented in this file.

## [0.1.2] - 2026-07-28

### Added

- Bundle the English and Simplified Chinese OCR runtime in the Windows
  installer so scanned PDFs work without a separate Tesseract installation.
- Report partial PDF parsing results and failed page counts without discarding
  text extracted successfully from other pages.

### Fixed

- Prevent course header action labels from collapsing into vertical text at
  intermediate viewport widths.
- Prevent completed section rows and expanded study history from overflowing
  the course page in standard and large font modes.
- Present chapter and section materials in a modal instead of expanding them at
  the top of the course page.

### Changed

- Allow multiple successfully parsed materials to be marked as priority
  material in the same course scope.

### Notes

- The v0.1.2 Windows assets were refreshed on 2026-08-04. The current
  installer supersedes earlier v0.1.2 builds while preserving the same version
  number and existing local learning data during an upgrade.

## [0.1.1] - 2026-07-28

### Fixed

- Prevent model connection status from remaining in a loading state when a
  Codex or Antigravity probe stalls.
- Clean up cancelled Codex App Server requests and partially initialized
  processes.
- Replace verbose Antigravity login diagnostics with a concise connection
  prompt.

### Changed

- Probe provider status and model options concurrently with bounded backend and
  frontend timeouts.
- Support the current official npm Codex platform-package executable layout.

## [0.1.0] - 2026-07-23

### Added

- Course, chapter, section, and recurring study-record management.
- Guided recall, reconstruction, practice, correction, and next-question flow.
- Codex-based learning tasks and optional Gemini note polishing through local CLIs.
- PDF, URL, public-video transcript, OCR, full-text, and optional semantic material search.
- Structured 12-question practice, per-question review, and mistake tracking.
- Obsidian Markdown editing, preview, search, backup, restore, and export.
- Read-only MIT OpenCourseWare example showing the complete workflow.
- Self-contained Windows x64 installer with selectable install location and safe uninstall.

### Notes

- This is the first public preview.
- The application interface is currently Simplified Chinese.
- The Windows installer is not code-signed yet.

[0.1.2]: https://github.com/Throb7777/lumina-study-coach/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Throb7777/lumina-study-coach/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Throb7777/lumina-study-coach/releases/tag/v0.1.0
