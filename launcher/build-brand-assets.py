from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def contain_alpha(image: Image.Image, canvas_size: int = 1024, padding: int = 48) -> Image.Image:
    rgba = image.convert("RGBA")
    bounds = rgba.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("The source icon has no visible pixels.")
    cropped = rgba.crop(bounds)
    target = canvas_size - (padding * 2)
    cropped.thumbnail((target, target), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    x = (canvas_size - cropped.width) // 2
    y = (canvas_size - cropped.height) // 2
    canvas.alpha_composite(cropped, (x, y))
    return canvas


def flattened_icon(icon: Image.Image, size: int, color: tuple[int, int, int]) -> Image.Image:
    background = Image.new("RGB", (size, size), color)
    resized = icon.resize((size, size), Image.Resampling.LANCZOS)
    background.paste(resized, mask=resized.getchannel("A"))
    return background


def write_size_check(icon: Image.Image, destination: Path) -> None:
    canvas = Image.new("RGB", (1200, 520), "#F8F5EF")
    draw = ImageDraw.Draw(canvas)
    samples = (256, 128, 64, 32, 16)
    x = 48
    for size in samples:
        preview_size = max(size, 96)
        preview = flattened_icon(icon, size, (248, 245, 239))
        if preview_size != size:
            preview = preview.resize((preview_size, preview_size), Image.Resampling.NEAREST)
        canvas.paste(preview, (x, 58))
        draw.text((x, 58 + preview_size + 14), f"{size}px", fill="#49372D")
        x += preview_size + 48

    x = 48
    for size in samples:
        preview_size = max(size, 96)
        preview = flattened_icon(icon, size, (40, 37, 35))
        if preview_size != size:
            preview = preview.resize((preview_size, preview_size), Image.Resampling.NEAREST)
        canvas.paste(preview, (x, 302))
        draw.text((x, 302 + preview_size + 14), f"{size}px dark", fill="#49372D")
        x += preview_size + 48
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Lumina icon assets from an alpha PNG.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    root = args.root.resolve()
    master = contain_alpha(Image.open(args.source))
    master_path = root / "design-references" / "brand" / "lumina-icon-master.png"
    ico_path = root / "launcher" / "assets" / "lumina.ico"
    frontend = root / "frontend" / "public"

    master_path.parent.mkdir(parents=True, exist_ok=True)
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    frontend.mkdir(parents=True, exist_ok=True)

    master.save(master_path, optimize=True)
    master.save(ico_path, format="ICO", sizes=[(size, size) for size in ICON_SIZES])
    for name, size in (
        ("favicon-32.png", 32),
        ("favicon-192.png", 192),
        ("apple-touch-icon.png", 180),
    ):
        master.resize((size, size), Image.Resampling.LANCZOS).save(frontend / name, optimize=True)
    write_size_check(master, root / "design-references" / "brand" / "lumina-icon-size-check.png")


if __name__ == "__main__":
    main()
