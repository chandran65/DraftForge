import os
import sys
import logging
import subprocess

# Set up logging for verification
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] TestSuite: %(message)s")
logger = logging.getLogger("test_suite")

def create_synthetic_blueprint_image(file_path):
    """
    Generates a synthetic raster blueprint image using PIL (Pillow) to serve as a 
    valid, reproducible test input for Path B (CV line extraction).
    """
    logger.info(f"Generating synthetic raster blueprint image: {file_path}")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("PIL (Pillow) is required for creating test blueprints. Run pip install -r requirements.txt")
        raise
        
    # Standard white background canvas (800 x 600)
    img = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(img)
    
    # Draw simple part shapes (concentric squares and circular bores)
    # Visible edges (Black lines)
    draw.rectangle([100, 100, 700, 500], outline="black", width=3)
    draw.rectangle([250, 200, 550, 400], outline="black", width=2)
    
    # Internal bore circle
    draw.ellipse([350, 250, 450, 350], outline="black", width=2)
    
    # Horizontal Axis centerline (simulated centerlines with dots/dashes)
    draw.line([50, 300, 750, 300], fill="black", width=1)
    # Vertical Axis centerline
    draw.line([400, 50, 400, 550], fill="black", width=1)
    
    # Dimension Callouts
    draw.text((410, 230), "DIA 100", fill="black")
    draw.text((260, 180), "LENGTH: 300mm", fill="black")
    draw.text((110, 80), "OUTER FLANGE: 600mm", fill="black")
    
    img.save(file_path)
    logger.info("Synthetic drawing image generated successfully.")

def run_pipeline_cli(args):
    """
    Helper to invoke the CLI script as a subprocess, matching direct terminal execution.
    """
    cmd = [sys.executable, "pipeline.py"] + args
    logger.info(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"Execution failed!\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        return False
        
    logger.info("Command completed successfully.")
    return True

def run_tests():
    logger.info("=" * 60)
    logger.info("Starting Pipeline Integration and Verification Tests")
    logger.info("=" * 60)
    
    # Ensure standard directory context
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Define file names
    test_img_input = "test_synthetic_drawing.png"
    test_igs_input = "test_synthetic_cad.igs"
    
    output_pdf_base = "test_drawing_output"
    output_cad_base = "test_cad_output"
    
    # Clean up old test artifacts if any
    for f in [test_img_input, f"{output_pdf_base}.svg", f"{output_pdf_base}.pdf", f"{output_cad_base}.svg", f"{output_cad_base}.pdf"]:
        if os.path.exists(f):
            os.remove(f)
            
    try:
        # Create synthetic input image for Path B
        create_synthetic_blueprint_image(test_img_input)
        
        # Create a dummy mock 3D file for Path A (the parser doesn't inspect the content in mock mode)
        with open(test_igs_input, "w") as f:
            f.write("DUMMY CAD IGES METADATA FILE FOR TESTING")
            
        success = True
        
        # Test 1: Run Path B (Image OpenCV parsing) with Dark Theme
        logger.info("\n--- TEST 1: Path B OpenCV Image extraction (Dark Theme) ---")
        t1_args = ["--input", test_img_input, "--output", output_pdf_base, "--path", "pdf", "--theme", "dark"]
        if run_pipeline_cli(t1_args):
            svg_exists = os.path.exists(f"{output_pdf_base}.svg")
            pdf_exists = os.path.exists(f"{output_pdf_base}.pdf")
            logger.info(f"Generated SVG exists: {svg_exists} (size: {os.path.getsize(f'{output_pdf_base}.svg') if svg_exists else 0} bytes)")
            logger.info(f"Generated PDF exists: {pdf_exists} (size: {os.path.getsize(f'{output_pdf_base}.pdf') if pdf_exists else 0} bytes)")
            if not (svg_exists and pdf_exists):
                logger.error("Test 1 Failed: Target output files missing!")
                success = False
        else:
            success = False
            
        # Test 2: Run Path A (CAD projection parser) with Light Theme
        logger.info("\n--- TEST 2: Path A CAD dynamic projections (Light Theme) ---")
        t2_args = ["--input", test_igs_input, "--output", output_cad_base, "--path", "cad", "--theme", "light"]
        if run_pipeline_cli(t2_args):
            svg_exists = os.path.exists(f"{output_cad_base}.svg")
            pdf_exists = os.path.exists(f"{output_cad_base}.pdf")
            logger.info(f"Generated SVG exists: {svg_exists} (size: {os.path.getsize(f'{output_cad_base}.svg') if svg_exists else 0} bytes)")
            logger.info(f"Generated PDF exists: {pdf_exists} (size: {os.path.getsize(f'{output_cad_base}.pdf') if pdf_exists else 0} bytes)")
            if not (svg_exists and pdf_exists):
                logger.error("Test 2 Failed: Target output files missing!")
                success = False
        else:
            success = False
            
        # Test 3: Auto Path Detection
        logger.info("\n--- TEST 3: CLI automatic extension matching ---")
        t3_args = ["--input", test_img_input, "--output", "test_auto_output", "--path", "auto"]
        if run_pipeline_cli(t3_args):
            svg_exists = os.path.exists("test_auto_output.svg")
            if svg_exists:
                logger.info("Auto path mapping successfully resolved extension matching!")
                os.remove("test_auto_output.svg")
                if os.path.exists("test_auto_output.pdf"):
                    os.remove("test_auto_output.pdf")
            else:
                logger.error("Test 3 Failed: Target output file missing!")
                success = False
        else:
            success = False
            
        # Cleaning up generated source files
        for f in [
            test_img_input,
            test_igs_input,
            f"{output_pdf_base}.svg",
            f"{output_pdf_base}.pdf",
            f"{output_pdf_base}.png",
            f"{output_cad_base}.svg",
            f"{output_cad_base}.pdf",
            f"{output_cad_base}.png",
            "test_auto_output.svg",
            "test_auto_output.pdf",
            "test_auto_output.png",
        ]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    logger.warning(f"Could not remove temporary test file {f}: {e}")
            
        logger.info("\n" + "=" * 60)
        if success:
            logger.info("ALL INTEGRATION TESTS PASSED TRIUMPHANTLY!")
        else:
            logger.error("SOME INTEGRATION TESTS ENCOUNTERED ERRORS.")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.exception(f"Exception during testing: {e}")
        
if __name__ == "__main__":
    run_tests()
