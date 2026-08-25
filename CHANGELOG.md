# Changelog

All notable public changes to Lumina are documented in this file.

## [0.1.3] - 2026-08-09

### Added

- Add AI-guided recall and reconstruction questions with per-question checking,
  while keeping one open recall field for the learner's own retrieval.
- Allow non-choice practice responses to include compact image or PDF
  attachments, with bounded file validation and lifecycle cleanup.
- Add portable backup import so courses, study records, materials, referenced
  response attachments, settings, and managed notes can move to another Lumina
  installation.

### Fixed

- Carry the previous study record's preview questions into the next record and
  review earlier learning instead of the material that is about to be studied.
- Avoid duplicated or overly broad AI practice questions and hide unavailable
  previous/next navigation actions at the ends of a practice set.
- Render legacy Markdown, escaped LaTeX, and control-character notation
  consistently across summaries, notes, practice, and mistake review.
- Keep unrelated study controls usable while an AI task is running and dismiss
  transient generation confirmations automatically.
- Recover completed section-note drafts when safe malformed LaTeX control
  characters are present, stop unrecoverable result polling, and provide an
  explicit retry action for the saved generation run.

### Changed

- Simplify mistake collection around the original question, correct answer,
  learner note, and compact error-type selection.
- Auto-collapse course study history after navigation and completion.
- Remove internal material references and grading evidence from learner-facing
  notes and practice feedback, and standardise related action sizes.

### Notes

- The v0.1.3 Windows assets were refreshed on 2026-08-25 with the section-note
  result recovery fix. The version number remains unchanged and existing local
  learning data is preserved during an upgrade.

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

[0.1.3]: https://github.com/Throb7777/lumina-study-coach/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Throb7777/lumina-study-coach/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Throb7777/lumina-study-coach/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Throb7777/lumina-study-coach/releases/tag/v0.1.0
