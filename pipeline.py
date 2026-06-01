#!/usr/bin/env python
"""
3D→2D Pipeline CLI Orchestrator
Converts 3D CAD models or 2D technical drawings/blueprints into premium SVGs and PDFs.
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Configure modular logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("3d2d_pipeline")

# Add local path import fallback if executed from other directories
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cad_parser import project_3d_cad, HAS_FREECAD
from pdf_parser import parse_drawing
from renderer import render_pipeline_output, THEMES

def parse_args():
    parser = argparse.ArgumentParser(
        description="Automated 3D→2D CAD and drawing vector projection pipeline.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input 3D model (IGS/STEP) or 2D blueprint (PDF/PNG/JPG)."
    )
    parser.add_argument(
        "--output", "-o",
        default="output_drawing",
        help="Base name/path for generated output files (without extension)."
    )
    parser.add_argument(
        "--path", "-p",
        choices=["cad", "pdf", "auto"],
        default="auto",
        help="Force pipeline execution path:\n"
             "  cad: Load 3D model and project orthographic views\n"
             "  pdf: Parse 2D PDF vectors or raster lines\n"
             "  auto: Infer based on file extension (default)"
    )
    parser.add_argument(
        "--theme", "-t",
        choices=list(THEMES.keys()),
        default="light",
        help="Aesthetic rendering theme for the final technical drawing. (default: light)"
    )
    parser.add_argument(
        "--views", "-v",
        nargs="+",
        default=["top", "front", "side"],
        help="CAD orthographic views to project (only applies to 'cad' path).\n"
             "Options: top front side iso (default: top front side)"
    )
    
    return parser.parse_args()

def auto_detect_path(file_path):
    """
    Infers the correct processing path (cad or pdf) based on the file extension.
    """
    _, ext = os.path.splitext(file_path.lower())
    cad_exts = {".igs", ".iges", ".step", ".stp"}
    pdf_img_exts = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
    
    if ext in cad_exts:
        return "cad"
    elif ext in pdf_img_exts:
        return "pdf"
    else:
        logger.warning(f"Unrecognized file extension '{ext}'. defaulting to 'pdf' path.")
        return "pdf"

def main():
    args = parse_args()
    
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Initializing 3D→2D Automated Drafting Pipeline")
    logger.info("=" * 60)
    
    # 1. Validate Input
    if not os.path.exists(args.input):
        logger.error(f"Input file not found at: '{args.input}'")
        sys.exit(1)
        
    # 2. Determine execution path
    exec_path = args.path
    if exec_path == "auto":
        exec_path = auto_detect_path(args.input)
        logger.info(f"Auto-detected execution path: '{exec_path}'")
        
    geometry_data = None
    
    try:
        # 3. Process Input Path
        if exec_path == "cad":
            logger.info("Starting Path A: 3D CAD Orthographic Projections")
            # If FreeCAD is native, we project views to an SVG directly,
            # otherwise we fall back to generating our structured multi-view mock.
            geometry_data = project_3d_cad(args.input, f"{args.output}.svg", views=args.views)
            
        elif exec_path == "pdf":
            logger.info("Starting Path B: 2D drawing vector/raster extraction")
            geometry_data = parse_drawing(args.input)
            
        if not geometry_data:
            raise ValueError("Processing returned empty geometry metadata.")
            
        # 4. Invoke Common Rendering Stage
        # (This combines geometries, overlays titles, scale labels, borders, and renders SVG + PDF)
        logger.info("Entering Unified Blueprint Canvas & Drafting Renderer")
        svg_out, pdf_out = render_pipeline_output(geometry_data, args.output, theme_name=args.theme)
        
        # 5. Output Results Summary
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("Pipeline Execution Complete!")
        logger.info(f"Time Elapsed:   {elapsed:.2f} seconds")
        logger.info(f"Source Format:  {geometry_data.get('source', 'Unknown')}")
        logger.info(f"SVG Vector:     {os.path.abspath(svg_out)}")
        logger.info(f"PDF Vector:     {os.path.abspath(pdf_out)}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.exception(f"Pipeline encountered a critical error during execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
