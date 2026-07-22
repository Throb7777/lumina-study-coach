from __future__ import annotations

import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def ico_sizes(path: Path) -> set[tuple[int, int]]:
    data = path.read_bytes()
    reserved, image_type, count = struct.unpack("<HHH", data[:6])
    if reserved != 0 or image_type != 1:
        raise AssertionError(f"not an ICO: {path}")
    sizes: set[tuple[int, int]] = set()
    for index in range(count):
        width, height = struct.unpack("BB", data[6 + index * 16 : 8 + index * 16])
        sizes.add((width or 256, height or 256))
    return sizes


class BrandAssetTests(unittest.TestCase):
    def test_windows_icon_contains_all_supported_sizes(self) -> None:
        self.assertEqual(
            ico_sizes(ROOT / "launcher/assets/lumina.ico"),
            {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)},
        )

    def test_web_and_reference_assets_have_expected_dimensions(self) -> None:
        self.assertEqual(
            png_size(ROOT / "design-references/brand/lumina-icon-master.png"),
            (1024, 1024),
        )
        self.assertEqual(png_size(ROOT / "frontend/public/favicon-32.png"), (32, 32))
        self.assertEqual(png_size(ROOT / "frontend/public/favicon-192.png"), (192, 192))
        self.assertEqual(png_size(ROOT / "frontend/public/apple-touch-icon.png"), (180, 180))


if __name__ == "__main__":
    unittest.main()
