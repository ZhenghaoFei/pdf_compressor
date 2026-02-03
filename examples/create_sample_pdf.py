#!/usr/bin/env python3
"""
Create a small sample PDF with an embedded image for demo/testing.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> int:
    here = Path(__file__).resolve().parent
    out_pdf = here / "sample.pdf"
    img_path = here / "sample_image.png"

    img = Image.new("RGB", (800, 600), color=(240, 245, 250))
    draw = ImageDraw.Draw(img)
    for i in range(0, 800, 40):
        draw.line((i, 0, i, 600), fill=(180, 200, 230), width=3)
    draw.rectangle((80, 80, 720, 520), outline=(60, 90, 130), width=6)
    draw.text((120, 120), "Sample Image", fill=(30, 60, 100))
    img.save(img_path, format="PNG")

    # PIL can write a single-image PDF directly.
    img.save(out_pdf, format="PDF", resolution=150.0)

    # Keep the image for reference; it is small and useful for debugging.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
