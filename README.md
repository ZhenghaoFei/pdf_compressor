# PDF Image Compressor (Python)

![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)

Compress images inside a PDF by re-encoding them as JPEG with configurable parameters.

**Features**
- Re-encode embedded images as JPEG.
- Control JPEG quality, optimization, and progressive output.
- Skip replacement when recompressed images are not smaller.

**Requirements**
- Python 3.10+

**Quick Start**
```bash
pip install -r requirements.txt
python compress_pdf.py -i input.pdf -q 70
```

**Install**
```bash
pip install -r requirements.txt
```

**Usage**
```bash
# Output to input_compressed.pdf in same directory
python compress_pdf.py -i input.pdf -q 70

# Or specify custom output path
python compress_pdf.py -i input.pdf -o output.pdf -q 70
```
The script prints a summary including image counts, input/output PDF sizes, and a
breakdown of image/content/font/metadata streams plus container overhead.

Short flags are available (e.g. `-q` for quality). JPEG optimization is enabled by default;
use `--no-optimize` to disable. Skip-smaller is enabled by default; use
`--no-skip-smaller` to disable.

**CLI Flags**
- `-i`, `--input` Input PDF path or directory (required)
- `-o`, `--output` Output PDF path or directory (optional)
  - Single file without `-o`: creates `input_compressed.pdf` in same directory
  - Directory without `-o`: creates `file_compressed.pdf` for each PDF in place
  - With `-o folder`: all compressed files go into the specified folder
- `-q`, `--quality` JPEG quality (1-95), default 75
- `-q`, `--quality` JPEG quality (1-95), default 75
- `-O`, `--optimize` Enable JPEG optimizer (default on)
- `--no-optimize` Disable JPEG optimizer
- `-p`, `--progressive` Save progressive JPEGs
- `-s`, `--skip-smaller` Skip replacement if recompressed image is not smaller (default on)
- `--no-skip-smaller` Do not skip replacements even if recompressed image is larger
- `-a`, `--replace-alpha` Replace alpha/mask images by compositing on white
- `-r`, `--recursive` When input is a directory, process PDFs recursively

**Batch Compress a Folder**
```bash
# In-place: each file gets _compressed.pdf suffix
python compress_pdf.py -i input_folder -q 70

# Recursive: include subfolders
python compress_pdf.py -i input_folder -q 70 -r

# Or specify output folder (all files go into single folder)
python compress_pdf.py -i input_folder -o output_folder -q 70
```

**Alpha/Mask Images**
By default, images with transparency (alpha or masks) are skipped. To replace them,
composite on white:
```bash
python compress_pdf.py -i input.pdf -a
```

**Create a Sample PDF**
```bash
pip install -r requirements-dev.txt
python examples/create_sample_pdf.py
```
This generates `examples/sample.pdf` with an embedded image for demo/testing.

**Run Tests**
```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -p "test_*.py" -v
```

**License**
MIT

**Notes**
- This tool replaces image XObjects only. It does not downscale images.
- PDFs containing vector graphics are unaffected.
