# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A PDF image compressor that re-encodes embedded images as JPEG with configurable quality. It iterates through PDF pages, finds image XObjects, and replaces them with JPEG-encoded streams.

**Dependencies:** `pikepdf` for PDF manipulation, `Pillow` for image processing.

## Common Commands

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run compression
```bash
# Auto-generates input_compressed.pdf in same directory
python compress_pdf.py -i input.pdf -q 70

# Or specify custom output path
python compress_pdf.py -i input.pdf -o output.pdf -q 70
```

### Batch compress a folder
```bash
# In-place: each file gets _compressed.pdf suffix (use -r for subfolders)
python compress_pdf.py -i input_folder -q 70
python compress_pdf.py -i input_folder -q 70 -r  # recursive

# Or specify output folder (all files go into single folder)
python compress_pdf.py -i input_folder -o output_folder -q 70
```

### Run tests
```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -p "test_*.py" -v
```

### Create sample PDF for testing
```bash
pip install -r requirements-dev.txt
python examples/create_sample_pdf.py
```

## Architecture

**Main file:** `compress_pdf.py` - single-file script with CLI entry point at `main()`

**Core flow:**
1. `compress_pdf()` - processes a single PDF, returns count of images replaced and summary stats
2. `compress_folder()` - batch processes PDFs in a directory, aggregates stats
3. `_iter_image_xobjects()` - recursively iterates image XObjects including those nested in Form XObjects
4. `_collect_pdf_stats()` - analyzes PDF structure to report bytes by category (image/content/font/metadata/other/overhead)

**Image processing:**
- Uses `pikepdf.PdfImage.as_pil_image()` to extract images
- Converts to RGB JPEG with configurable quality, optimization, progressive encoding
- Optionally skips images with alpha/mask (use `-a` to composite on white)
- Replaces original stream with new `pikepdf.Stream` with `/DCTDecode` filter

**Tests:** Located in `tests/test_compress.py`, use `reportlab` to generate test PDFs with embedded images.
