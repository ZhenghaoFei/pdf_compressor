from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from compress_pdf import compress_pdf


def _make_pdf_with_image(path: Path) -> None:
    img = Image.new("RGB", (1200, 800), color=(230, 235, 240))
    draw = ImageDraw.Draw(img)
    for i in range(0, 1200, 50):
        draw.line((i, 0, i, 800), fill=(160, 180, 210), width=4)
    draw.text((100, 100), "Test Image", fill=(40, 60, 90))
    img_path = path.with_suffix(".png")
    img.save(img_path, format="PNG")

    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 72, "Compression Test")
    c.drawImage(str(img_path), 72, height - 72 - 420, width=468, height=312)
    c.showPage()
    c.save()


class CompressPdfTest(unittest.TestCase):
    def test_compress_pdf(self) -> None:
        tmp = Path(self._testMethodName)
        tmp.mkdir(exist_ok=True)
        input_pdf = tmp / "input.pdf"
        output_pdf = tmp / "output.pdf"

        _make_pdf_with_image(input_pdf)

        replaced, summary = compress_pdf(
            str(input_pdf),
            str(output_pdf),
            quality=60,
            optimize=True,
            progressive=True,
            skip_smaller=False,
            replace_alpha=False,
        )

        self.assertTrue(output_pdf.exists())
        self.assertGreaterEqual(replaced, 1)
        self.assertGreater(output_pdf.stat().st_size, 0)
        self.assertEqual(summary["replaced"], replaced)
        self.assertIn("total_original_bytes", summary)
        self.assertIn("total_new_bytes", summary)
        self.assertIn("input_stats", summary)
        self.assertIn("output_stats", summary)

    def test_replace_alpha(self) -> None:
        tmp = Path(self._testMethodName)
        tmp.mkdir(exist_ok=True)
        input_pdf = tmp / "input_alpha.pdf"
        output_pdf = tmp / "output_alpha.pdf"

        img = Image.new("RGBA", (600, 400), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle((50, 50, 550, 350), fill=(0, 120, 200, 160))
        img_path = tmp / "alpha.png"
        img.save(img_path, format="PNG")

        c = canvas.Canvas(str(input_pdf), pagesize=letter)
        width, height = letter
        c.drawImage(str(img_path), 72, height - 72 - 320, width=400, height=266, mask="auto")
        c.showPage()
        c.save()

        replaced, summary = compress_pdf(
            str(input_pdf),
            str(output_pdf),
            quality=70,
            optimize=True,
            progressive=False,
            skip_smaller=False,
            replace_alpha=True,
        )

        self.assertTrue(output_pdf.exists())
        self.assertGreater(output_pdf.stat().st_size, 0)
        self.assertEqual(summary["replaced"], replaced)


if __name__ == "__main__":
    unittest.main()
