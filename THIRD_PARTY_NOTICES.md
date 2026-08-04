# Third-party notices

Lumina source code is distributed under the Apache License 2.0. Third-party
packages retain their own licenses; the exact installed versions are recorded
in `frontend/package-lock.json` and `backend/uv.lock`.

Release builds also provide a machine-readable software bill of materials
(SBOM). The lock files and SBOM are the authoritative complete version inventory.

## Bundled fonts

Lumina bundles Nunito Sans Variable and Noto Sans SC Variable through the
Fontsource packages. Both font families retain the SIL Open Font License 1.1.
They are used locally and are not loaded from a CDN.

## Built-in example course

`frontend/src/data/example-course.json` is a static, read-only learning example
derived from MIT OpenCourseWare 18.06 Linear Algebra, Lecture 1 materials:

- Course page: https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/resources/lecture-1-the-geometry-of-linear-equations/
- Transcript: https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/50702172c7cdc969615b81e6f22499fd_MIT18_06S10_L01.pdf
- MIT OpenCourseWare terms: https://ocw.mit.edu/pages/privacy-and-terms-of-use/

The example content is provided under Creative Commons Attribution-
NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0), not under the
repository's Apache License 2.0. Its source attribution is also displayed in
the application and documented in `frontend/src/data/EXAMPLE_LICENSE.md`.

## Local material processing

Lumina uses the following local components. They are not part of the repository
source license and retain their own licenses:

- Tesseract OCR and the `tessdata_best` `chi_sim` / `chi_sim_vert` / `eng`
  language data:
  Apache License 2.0. Windows release packages include the OCR runtime and all
  three language files so PDF parsing does not require a separate installation.
- `pypdfium2` and PDFium for rendering scanned PDF pages: Apache License 2.0
  and BSD-style component licenses as documented by that project.
- FastEmbed and the optional
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` ONNX model:
  Apache License 2.0. The model is downloaded only after the user enables
  semantic search and is stored under the ignored `runtime-data/search-models/`
  directory.

Derived OCR caches and search indexes contain local material text. They remain
inside ignored runtime storage and are excluded from source control and Lumina
backup archives.

## Windows packaging

Windows release artifacts are built with:

- PyInstaller, distributed under GPL-2.0-or-later with its bootloader exception.
  The exception permits distributing the resulting bundled application under
  Lumina's license while PyInstaller itself retains its license.
- Inno Setup, Copyright (C) 1997-2026 Jordan Russell and contributors, under
  the Inno Setup license. The generated setup program contains the Inno Setup
  runtime.
- `installer/languages/ChineseSimplified.isl`, sourced from the Inno Setup
  project at
  https://github.com/jrsoftware/issrc/tree/main/Files/Languages and retaining
  its original translator and license notices.
