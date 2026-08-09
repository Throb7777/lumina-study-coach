from __future__ import annotations

import re
from contextlib import suppress
from pathlib import Path, PurePath

from app.materials import MaterialError, extract_image_text, extract_pdf_detailed

MAX_ANSWER_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ANSWER_ATTACHMENTS = 5
MAX_ANSWER_ATTACHMENT_PDF_PAGES = 12
MAX_ANSWER_ATTACHMENT_TEXT_CHARS = 50_000
MAX_ANSWER_RESPONSE_TEXT_CHARS = 100_000
MAX_ANSWER_IMAGE_DIMENSION = 20_000
MAX_ANSWER_IMAGE_PIXELS = 40_000_000


class AnswerAttachmentError(RuntimeError):
    pass


def detected_media_type(content: bytes) -> tuple[str, str]:
    if content.startswith(b"%PDF"):
        return "application/pdf", ".pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise AnswerAttachmentError("请选择 PDF、PNG、JPG 或 WebP 文件")


def safe_original_name(value: str | None, extension: str) -> str:
    name = PurePath((value or "").replace("\\", "/")).name.strip()
    if not name:
        name = f"answer{extension}"
    name = re.sub(r"[\x00-\x1f]", "", name)
    return name[:300] or f"answer{extension}"


def _jpeg_dimensions(content: bytes) -> tuple[int, int] | None:
    offset = 2
    start_of_frame_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while offset + 3 < len(content):
        if content[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(content) and content[offset] == 0xFF:
            offset += 1
        if offset >= len(content):
            break
        marker = content[offset]
        offset += 1
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(content):
            break
        segment_length = int.from_bytes(content[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(content):
            break
        if marker in start_of_frame_markers and segment_length >= 7:
            height = int.from_bytes(content[offset + 3 : offset + 5], "big")
            width = int.from_bytes(content[offset + 5 : offset + 7], "big")
            return width, height
        offset += segment_length
    return None


def image_dimensions(content: bytes, media_type: str) -> tuple[int, int]:
    dimensions: tuple[int, int] | None = None
    if media_type == "image/png" and len(content) >= 24 and content[12:16] == b"IHDR":
        dimensions = (
            int.from_bytes(content[16:20], "big"),
            int.from_bytes(content[20:24], "big"),
        )
    elif media_type == "image/jpeg":
        dimensions = _jpeg_dimensions(content)
    elif media_type == "image/webp" and len(content) >= 30:
        chunk_type = content[12:16]
        if chunk_type == b"VP8X":
            dimensions = (
                int.from_bytes(content[24:27], "little") + 1,
                int.from_bytes(content[27:30], "little") + 1,
            )
        elif chunk_type == b"VP8L" and content[20] == 0x2F:
            bits = int.from_bytes(content[21:25], "little")
            dimensions = ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
        elif chunk_type == b"VP8 " and content[23:26] == b"\x9d\x01\x2a":
            dimensions = (
                int.from_bytes(content[26:28], "little") & 0x3FFF,
                int.from_bytes(content[28:30], "little") & 0x3FFF,
            )
    if dimensions is None or dimensions[0] <= 0 or dimensions[1] <= 0:
        raise AnswerAttachmentError("无法读取图片尺寸，请确认文件未损坏")
    return dimensions


def validate_image_dimensions(content: bytes, media_type: str) -> None:
    if not media_type.startswith("image/"):
        return
    width, height = image_dimensions(content, media_type)
    if (
        width > MAX_ANSWER_IMAGE_DIMENSION
        or height > MAX_ANSWER_IMAGE_DIMENSION
        or width * height > MAX_ANSWER_IMAGE_PIXELS
    ):
        raise AnswerAttachmentError(
            "图片分辨率过高，请缩小到 4000 万像素以内且单边不超过 20000 像素"
        )


def extract_attachment_text(path: Path, media_type: str) -> str:
    try:
        if media_type == "application/pdf":
            extraction = extract_pdf_detailed(
                path,
                max_pages=MAX_ANSWER_ATTACHMENT_PDF_PAGES,
                use_ocr_cache=False,
                ocr_timeout_seconds=60,
                ocr_command_timeout_seconds=20,
                ocr_page_segmentation_modes=(3, 6),
            )
            return "\n\n".join(
                f"{heading}\n{text}" if heading else text
                for heading, _page, text in extraction.chunks
            ).strip()
        return extract_image_text(
            path,
            timeout_seconds=40,
            page_segmentation_modes=(3, 6),
        ).strip()
    except MaterialError as error:
        raise AnswerAttachmentError(str(error)) from error


def resolve_attachment_path(root: Path, storage_path: str) -> Path:
    resolved_root = root.resolve()
    target = (resolved_root / storage_path).resolve()
    if not target.is_relative_to(resolved_root):
        raise AnswerAttachmentError("附件存储路径无效")
    return target


def remove_attachment_files(root: Path, storage_paths: list[str]) -> None:
    for storage_path in storage_paths:
        try:
            stored_file = resolve_attachment_path(root, storage_path)
        except AnswerAttachmentError:
            continue
        with suppress(OSError):
            stored_file.unlink(missing_ok=True)
            stored_file.parent.rmdir()
