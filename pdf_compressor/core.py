#!/usr/bin/env python3
"""
Compress images inside a PDF by re-encoding them as JPEG with user parameters.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import Tuple

import pikepdf
from PIL import Image


def _flatten_alpha(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    if img.mode == "P" and "transparency" in img.info:
        return img.convert("RGBA").convert("RGB")
    return img


def _to_jpeg_bytes(
    img: Image.Image, quality: int, optimize: bool, progressive: bool
) -> Tuple[bytes, Tuple[int, int]]:
    if img.mode in ("1", "L", "P"):
        img = img.convert("RGB")
    elif img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = _flatten_alpha(img)

    buf = io.BytesIO()
    img.save(
        buf,
        format="JPEG",
        quality=quality,
        optimize=optimize,
        progressive=progressive,
    )
    return buf.getvalue(), img.size


def _deref(obj):
    try:
        return obj.get_object()
    except AttributeError:
        return obj
    except Exception:
        return None


def _iter_image_xobjects(resources):
    xobjects = resources.get("/XObject", None)
    if xobjects is None:
        return
    for name, xobj in list(xobjects.items()):
        obj = _deref(xobj)
        if obj is None:
            continue
        subtype = obj.get("/Subtype", None)
        if subtype == "/Image":
            yield xobjects, name, obj
        elif subtype == "/Form":
            form_res = obj.get("/Resources", None)
            if form_res is not None:
                yield from _iter_image_xobjects(form_res)

def _collect_image_bytes(pdf: pikepdf.Pdf) -> Tuple[int, int]:
    total_images = 0
    total_bytes = 0
    for page in pdf.pages:
        resources = page.get("/Resources", None)
        if resources is None:
            continue
        for _xobjects, _name, obj in _iter_image_xobjects(resources):
            total_images += 1
            try:
                length = obj.get("/Length", 0)
            except Exception:
                length = 0
            if isinstance(length, int) and length > 0:
                total_bytes += length
    return total_images, total_bytes


def _get_stream_length(obj) -> int:
    try:
        length = obj.get("/Length", 0)
    except Exception:
        length = 0
    return length if isinstance(length, int) and length > 0 else 0


def _collect_pdf_stats(pdf: pikepdf.Pdf, file_path: Path) -> dict:
    file_size = file_path.stat().st_size
    objects = pdf.objects
    object_count = len(objects)
    stream_count = 0
    stream_bytes_total = 0

    for obj in objects:
        if isinstance(obj, pikepdf.Stream):
            stream_count += 1
            stream_bytes_total += _get_stream_length(obj)

    image_count = 0
    image_bytes = 0
    form_xobject_count = 0
    for page in pdf.pages:
        resources = page.get("/Resources", None)
        if resources is None:
            continue
        xobjects = resources.get("/XObject", None)
        if xobjects:
            for _name, xobj in list(xobjects.items()):
                obj = _deref(xobj)
                if obj is None:
                    continue
                subtype = obj.get("/Subtype", None)
                if subtype == "/Image":
                    image_count += 1
                    image_bytes += _get_stream_length(obj)
                elif subtype == "/Form":
                    form_xobject_count += 1

    content_bytes = 0
    for page in pdf.pages:
        contents = page.get("/Contents", None)
        if contents is None:
            continue
        if isinstance(contents, pikepdf.Stream):
            content_bytes += _get_stream_length(contents)
        else:
            try:
                for item in contents:
                    item_obj = _deref(item)
                    if isinstance(item_obj, pikepdf.Stream):
                        content_bytes += _get_stream_length(item_obj)
            except Exception:
                pass

    font_bytes = 0
    for page in pdf.pages:
        resources = page.get("/Resources", None)
        if resources is None:
            continue
        fonts = resources.get("/Font", None)
        if not fonts:
            continue
        for _name, fontref in list(fonts.items()):
            font = _deref(fontref)
            if font is None:
                continue
            descriptor = font.get("/FontDescriptor", None)
            if descriptor is None:
                continue
            descriptor = _deref(descriptor)
            for key in ("/FontFile", "/FontFile2", "/FontFile3"):
                stream = descriptor.get(key, None)
                if stream is None:
                    continue
                stream = _deref(stream)
                if isinstance(stream, pikepdf.Stream):
                    font_bytes += _get_stream_length(stream)

    metadata_bytes = 0
    try:
        metadata = pdf.root.get("/Metadata", None)
    except Exception:
        metadata = None
    if metadata is not None:
        metadata = _deref(metadata)
        if isinstance(metadata, pikepdf.Stream):
            metadata_bytes = _get_stream_length(metadata)

    other_stream_bytes = stream_bytes_total - (image_bytes + content_bytes + font_bytes + metadata_bytes)
    if other_stream_bytes < 0:
        other_stream_bytes = 0

    overhead_bytes = file_size - stream_bytes_total
    if overhead_bytes < 0:
        overhead_bytes = 0

    return {
        "file_bytes": file_size,
        "object_count": object_count,
        "stream_count": stream_count,
        "stream_bytes_total": stream_bytes_total,
        "image_count": image_count,
        "image_bytes": image_bytes,
        "form_xobject_count": form_xobject_count,
        "content_bytes": content_bytes,
        "font_bytes": font_bytes,
        "metadata_bytes": metadata_bytes,
        "other_stream_bytes": other_stream_bytes,
        "overhead_bytes": overhead_bytes,
    }


def compress_pdf(
    input_path: str,
    output_path: str,
    quality: int,
    optimize: bool,
    progressive: bool,
    skip_smaller: bool,
    replace_alpha: bool,
) -> int:
    replaced = 0
    total_images = 0
    skipped_mask = 0
    skipped_decode = 0
    skipped_not_smaller = 0
    total_original_bytes = 0
    total_new_bytes = 0
    with pikepdf.open(input_path) as pdf:
        for page in pdf.pages:
            resources = page.get("/Resources", None)
            if resources is None:
                continue

            for xobjects, name, obj in _iter_image_xobjects(resources):
                total_images += 1
                try:
                    original_size = obj.get("/Length", 0)
                except Exception:
                    original_size = 0
                if isinstance(original_size, int) and original_size > 0:
                    total_original_bytes += original_size

                has_mask = obj.get("/SMask", None) is not None or obj.get("/Mask", None) is not None
                if has_mask and not replace_alpha:
                    # Skip alpha/mask images since JPEG cannot represent transparency.
                    skipped_mask += 1
                    continue

                try:
                    pdf_image = pikepdf.PdfImage(obj)
                    img = pdf_image.as_pil_image()
                except Exception:
                    # Skip non-decodable images
                    skipped_decode += 1
                    continue

                if replace_alpha:
                    img = _flatten_alpha(img)

                jpeg_bytes, (w, h) = _to_jpeg_bytes(
                    img, quality=quality, optimize=optimize, progressive=progressive
                )

                if skip_smaller and original_size and len(jpeg_bytes) >= original_size:
                    skipped_not_smaller += 1
                    continue

                image_stream = pikepdf.Stream(
                    pdf,
                    jpeg_bytes,
                    Type=pikepdf.Name("/XObject"),
                    Subtype=pikepdf.Name("/Image"),
                    Width=w,
                    Height=h,
                    ColorSpace=pikepdf.Name("/DeviceRGB"),
                    BitsPerComponent=8,
                    Filter=pikepdf.Name("/DCTDecode"),
                )
                xobjects[name] = image_stream
                replaced += 1
                total_new_bytes += len(jpeg_bytes)

        pdf.save(output_path)

    with pikepdf.open(input_path) as in_pdf:
        input_stats = _collect_pdf_stats(in_pdf, Path(input_path))
    with pikepdf.open(output_path) as out_pdf:
        output_stats = _collect_pdf_stats(out_pdf, Path(output_path))

    summary = {
        "total_images": total_images,
        "replaced": replaced,
        "skipped_mask": skipped_mask,
        "skipped_decode": skipped_decode,
        "skipped_not_smaller": skipped_not_smaller,
        "total_original_bytes": total_original_bytes,
        "total_new_bytes": total_new_bytes,
        "input_stats": input_stats,
        "output_stats": output_stats,
    }
    return replaced, summary


def compress_folder(
    input_dir: str,
    output_dir: str | None,
    quality: int,
    optimize: bool,
    progressive: bool,
    skip_smaller: bool,
    replace_alpha: bool,
    recursive: bool,
) -> Tuple[int, dict]:
    input_path = Path(input_dir)
    output_path = Path(output_dir) if output_dir else None
    if output_path:
        output_path.mkdir(parents=True, exist_ok=True)

    pattern = "**/*.pdf" if recursive else "*.pdf"
    total_replaced = 0
    total_summary = {
        "total_images": 0,
        "replaced": 0,
        "skipped_mask": 0,
        "skipped_decode": 0,
        "skipped_not_smaller": 0,
        "total_original_bytes": 0,
        "total_new_bytes": 0,
        "files": 0,
        "input_stats": {
            "file_bytes": 0,
            "object_count": 0,
            "stream_count": 0,
            "stream_bytes_total": 0,
            "image_count": 0,
            "image_bytes": 0,
            "form_xobject_count": 0,
            "content_bytes": 0,
            "font_bytes": 0,
            "metadata_bytes": 0,
            "other_stream_bytes": 0,
            "overhead_bytes": 0,
        },
        "output_stats": {
            "file_bytes": 0,
            "object_count": 0,
            "stream_count": 0,
            "stream_bytes_total": 0,
            "image_count": 0,
            "image_bytes": 0,
            "form_xobject_count": 0,
            "content_bytes": 0,
            "font_bytes": 0,
            "metadata_bytes": 0,
            "other_stream_bytes": 0,
            "overhead_bytes": 0,
        },
    }

    for pdf_file in input_path.glob(pattern):
        # Skip files that are already compressed outputs
        if pdf_file.stem.endswith("_compressed"):
            continue
        if output_path:
            # Output to specified folder (flatten structure)
            out_file = output_path / pdf_file.name
        else:
            # In-place: add _compressed suffix to each file
            out_file = pdf_file.parent / f"{pdf_file.stem}_compressed{pdf_file.suffix}"
        replaced, summary = compress_pdf(
            str(pdf_file),
            str(out_file),
            quality=quality,
            optimize=optimize,
            progressive=progressive,
            skip_smaller=skip_smaller,
            replace_alpha=replace_alpha,
        )
        total_replaced += replaced
        total_summary["files"] += 1
        for key in (
            "total_images",
            "replaced",
            "skipped_mask",
            "skipped_decode",
            "skipped_not_smaller",
            "total_original_bytes",
            "total_new_bytes",
        ):
            total_summary[key] += summary[key]
        for key, value in summary["input_stats"].items():
            total_summary["input_stats"][key] += value
        for key, value in summary["output_stats"].items():
            total_summary["output_stats"][key] += value

    return total_replaced, total_summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compress images inside a PDF by re-encoding as JPEG."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input PDF path or directory",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=False,
        default=None,
        help="Output PDF path or directory (default: input_compressed.pdf in same folder)",
    )
    parser.add_argument(
        "-q",
        "--quality",
        type=int,
        default=75,
        help="JPEG quality (1-95). Default: 75",
    )
    parser.add_argument(
        "-O",
        "--optimize",
        action="store_true",
        default=True,
        help="Enable JPEG optimizer (default: on)",
    )
    parser.add_argument(
        "--no-optimize",
        action="store_false",
        dest="optimize",
        help="Disable JPEG optimizer",
    )
    parser.add_argument(
        "-p",
        "--progressive",
        action="store_true",
        help="Save progressive JPEGs",
    )
    parser.add_argument(
        "-s",
        "--skip-smaller",
        action="store_true",
        default=True,
        help="Skip replacement if recompressed image is not smaller (default: on)",
    )
    parser.add_argument(
        "--no-skip-smaller",
        action="store_false",
        dest="skip_smaller",
        help="Do not skip replacements even if recompressed image is larger",
    )
    parser.add_argument(
        "-a",
        "--replace-alpha",
        action="store_true",
        help="Replace alpha/mask images by compositing on white",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="When input is a directory, process PDFs recursively",
    )

    args = parser.parse_args()
    if not (1 <= args.quality <= 95):
        print("quality must be between 1 and 95", file=sys.stderr)
        return 2

    input_path = Path(args.input)
    if args.output is None:
        # Auto-generate output path
        if input_path.is_dir():
            # For directories, compress in-place when no output specified
            output_path = None
        else:
            output_path = input_path.parent / f"{input_path.stem}_compressed{input_path.suffix}"
    else:
        output_path = Path(args.output)
    if input_path.is_dir():
        replaced, summary = compress_folder(
            str(input_path),
            str(output_path) if output_path else None,
            quality=args.quality,
            optimize=args.optimize,
            progressive=args.progressive,
            skip_smaller=args.skip_smaller,
            replace_alpha=args.replace_alpha,
            recursive=args.recursive,
        )
    else:
        replaced, summary = compress_pdf(
            str(input_path),
            str(output_path),
            quality=args.quality,
            optimize=args.optimize,
            progressive=args.progressive,
            skip_smaller=args.skip_smaller,
            replace_alpha=args.replace_alpha,
        )
    print(f"Replaced {replaced} image(s).")
    def _fmt_bytes(n: int) -> str:
        if n >= 1024 * 1024:
            return f"{n / (1024 * 1024):.2f} MB"
        if n >= 1024:
            return f"{n / 1024:.1f} KB"
        return f"{n} B"

    print("Summary")
    print("-" * 60)
    print(
        f"Images found: {summary['total_images']} | "
        f"Replaced: {summary['replaced']} | "
        f"Skipped: mask={summary['skipped_mask']}, "
        f"decode={summary['skipped_decode']}, "
        f"not_smaller={summary['skipped_not_smaller']}"
    )
    inp = summary["input_stats"]
    out = summary["output_stats"]
    print(
        f"Input PDF size:  {_fmt_bytes(inp['file_bytes'])} | "
        f"Objects: {inp['object_count']} (streams: {inp['stream_count']})"
    )
    print(
        f"  Image streams: {_fmt_bytes(inp['image_bytes'])} "
        f"({inp['image_count']} images) | "
        f"Form XObjects: {inp['form_xobject_count']}"
    )
    print(
        f"  Content streams: {_fmt_bytes(inp['content_bytes'])} | "
        f"Fonts: {_fmt_bytes(inp['font_bytes'])} | "
        f"Metadata: {_fmt_bytes(inp['metadata_bytes'])}"
    )
    print(
        f"  Other streams: {_fmt_bytes(inp['other_stream_bytes'])} | "
        f"Overhead (xref/objects): {_fmt_bytes(inp['overhead_bytes'])}"
    )

    print(
        f"Output PDF size: {_fmt_bytes(out['file_bytes'])} | "
        f"Objects: {out['object_count']} (streams: {out['stream_count']})"
    )
    print(
        f"  Image streams: {_fmt_bytes(out['image_bytes'])} "
        f"({out['image_count']} images) | "
        f"Form XObjects: {out['form_xobject_count']}"
    )
    print(
        f"  Content streams: {_fmt_bytes(out['content_bytes'])} | "
        f"Fonts: {_fmt_bytes(out['font_bytes'])} | "
        f"Metadata: {_fmt_bytes(out['metadata_bytes'])}"
    )
    print(
        f"  Other streams: {_fmt_bytes(out['other_stream_bytes'])} | "
        f"Overhead (xref/objects): {_fmt_bytes(out['overhead_bytes'])}"
    )
    print(
        f"Re-encoded image bytes (new JPEG streams only): "
        f"{_fmt_bytes(summary['total_new_bytes'])}"
    )
    return 0
