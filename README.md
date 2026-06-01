# 🔥 DraftForge — 3D→2D CAD Drafting Engine

A modular, automated Python pipeline to convert 3D CAD files (IGS/STEP) and 2D engineering drawings (PDF/images) into high-fidelity, standardized 2D SVG vector graphics and PDF files.

---

## Architecture Overview

The pipeline has two specialized input paths feeding into a unified geometry representation and rendering stage:

```
                  ┌───────────────────────┐
                  │      Input File       │
                  └──────────┬────────────┘
                             │
              Is it a CAD (IGS/STEP) or Drawing (PDF/Img)?
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
       [ IGS / STEP ]                [ PDF / Image ]
     Path A (CAD Parser)          Path B (Drawing Parser)
    FreeCAD Headless & TechDraw    pdfplumber & OpenCV Hough
              │                             │
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
              │   Unified Geometry Data     │
              │  (Lines, Texts, Dimensions) │
              └──────────────┬───────────── ┘
                             ▼
              ┌─────────────────────────────┐
              │  Unified Canvas & Renderer  │
              │  (svgwrite & reportlab PDF) │
              └──────────────┬──────────────┘
                             ▼
                    ┌──────────────────┐
                    │  SVG & PDF Docs  │
                    └──────────────────┘
```

- **Path A (`cad_parser.py`)**: Utilizes headless FreeCAD to load 3D parts and uses the `TechDraw` module to dynamically project Front, Side, and Top orthographic views.
- **Path B (`pdf_parser.py`)**: Parses PDF drawings using `pdfplumber` to extract native vector geometry (lines, rects) and OCR/text, and uses computer vision (`pdf2image` + `opencv-python`) to apply Hough Line detection to raster images.
- **Unified Canvas (`renderer.py`)**: Draws clean technical drawings with standardised colors, scale scales, sheet margins, and dimensions.

---

## Setup & Dependencies

### 1. System Dependencies

#### PDF Rendering (Poppler)
`pdf2image` requires **poppler** to convert PDF pages into images for computer vision line detection.
- **macOS**: `brew install poppler`
- **Linux (Ubuntu/Debian)**: `sudo apt-get install poppler-utils`
- **Windows**: Download poppler and add the `bin/` folder to your System PATH.

#### FreeCAD (For 3D CAD Path A)
To run Path A natively, FreeCAD must be installed on your system.
- **macOS**: `brew install --cask freecad` (installed in `/Applications/FreeCAD.app`)
- **Linux**: `sudo apt-get install freecad`
- **Python Setup**: The pipeline dynamically attempts to detect standard FreeCAD library paths. If FreeCAD is installed in a non-standard location, you can set the `FREECAD_LIB_PATH` environment variable:
  ```bash
  export FREECAD_LIB_PATH="/Applications/FreeCAD.app/Contents/Resources/lib"
  ```
  *Note: If FreeCAD is not installed, the pipeline runs in a "Mock CAD Mode" for demonstration, producing drawing placeholders so testing does not break.*

### 2. Python Dependencies
Install the required packages:
```bash
pip install -r requirements.txt
```

---

## CLI Usage

Run the pipeline using the CLI entrypoint `pipeline.py`:

```bash
# Parse a 3D CAD file (IGS/STEP) and project views to SVG/PDF
python pipeline.py --input path/to/model.igs --output output_drawing --path cad

# Parse a 2D PDF drawing (vector or raster) and output clean vector paths
python pipeline.py --input path/to/drawing.pdf --output output_drawing --path pdf

# Parse an image drawing (PNG/JPG) using Hough Line detection
python pipeline.py --input path/to/blueprint.png --output output_drawing --path pdf
```

### Options:
- `--input`, `-i`: Path to the input file (IGS, STEP, PDF, PNG, JPG).
- `--output`, `-o`: Base name for the outputs (will generate `.svg` and `.pdf`).
- `--path`, `-p`: Explicitly force the pipeline path (`cad` or `pdf`). If not provided, it is auto-detected from the file extension.
- `--view`, `-v`: (For CAD path) Space-separated list of views to project. Options: `top`, `front`, `side`, `iso`. Defaults to all views.
