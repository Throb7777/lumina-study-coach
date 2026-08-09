from __future__ import annotations

from pathlib import Path

import pytest

import app.answer_attachments as attachment_module
from app.answer_attachments import (
    AnswerAttachmentError,
    extract_attachment_text,
    validate_image_dimensions,
)
from app.materials import PdfExtraction


def png_header(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
    )


def test_rejects_image_dimensions_that_are_too_large() -> None:
    with pytest.raises(AnswerAttachmentError, match="分辨率过高"):
        validate_image_dimensions(png_header(20_001, 100), "image/png")

    with pytest.raises(AnswerAttachmentError, match="4000 万像素"):
        validate_image_dimensions(png_header(10_000, 5_000), "image/png")


def test_rejects_image_when_dimensions_cannot_be_read() -> None:
    with pytest.raises(AnswerAttachmentError, match="无法读取图片尺寸"):
        validate_image_dimensions(b"\x89PNG\r\n\x1a\n", "image/png")


def test_pdf_attachment_uses_bounded_extraction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_extract(_path: Path, **kwargs: object) -> PdfExtraction:
        calls.append(kwargs)
        return PdfExtraction(
            chunks=[("第 1 页", 1, "答案")],
            total_pages=1,
            ocr_pages=0,
            failed_pages=(),
        )

    monkeypatch.setattr(attachment_module, "extract_pdf_detailed", fake_extract)

    assert extract_attachment_text(tmp_path / "answer.pdf", "application/pdf").endswith("答案")
    assert calls == [
        {
            "max_pages": 12,
            "use_ocr_cache": False,
            "ocr_timeout_seconds": 60,
            "ocr_command_timeout_seconds": 20,
            "ocr_page_segmentation_modes": (3, 6),
        }
    ]
