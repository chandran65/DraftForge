import os
import sys
import logging
import math

logger = logging.getLogger("3d2d_pipeline.cad_parser")

# Global flag to track FreeCAD availability
HAS_FREECAD = False
freecad_lib_path = None

def discover_freecad():
    """
    Search for standard FreeCAD library paths based on OS and sys.path,
    and attempt to import FreeCAD modules.
    """
    global HAS_FREECAD, freecad_lib_path
    
    # If the user explicitly provided a path via env var, check that first
    env_path = os.environ.get("FREECAD_LIB_PATH")
    paths_to_check = []
    if env_path:
        paths_to_check.append(env_path)
        
    # Standard installation paths based on platform
    if sys.platform == "darwin":  # macOS
        paths_to_check.extend([
            "/Applications/FreeCAD.app/Contents/Resources/lib",
            "/Applications/FreeCAD.app/Contents/lib",
            "/opt/homebrew/lib",
            "/opt/homebrew/opt/freecad/lib"
        ])
    elif sys.platform.startswith("linux"):  # Linux
        paths_to_check.extend([
            "/usr/lib/freecad/lib",
            "/usr/lib/freecad-python3/lib",
            "/usr/lib/freecad-daily/lib",
            "/usr/share/freecad/lib"
        ])
    elif sys.platform == "win32":  # Windows
        paths_to_check.extend([
            r"C:\Program Files\FreeCAD\bin",
            r"C:\Program Files\FreeCAD\lib",
            r"C:\Program Files (x86)\FreeCAD\bin"
        ])

    logger.info("Scanning for FreeCAD library path...")
    for path in paths_to_check:
        if os.path.exists(path):
            logger.info(f"Found potential FreeCAD directory: {path}")
            # Add to python path if not already there
            if path not in sys.path:
                sys.path.append(path)
            
            # Add bin if on Windows
            if sys.platform == "win32":
                bin_path = path.replace("\\lib", "\\bin")
                if os.path.exists(bin_path) and bin_path not in sys.path:
                    sys.path.append(bin_path)
                    
            try:
                # Attempt importing core modules
                import FreeCAD
                import Import
                import TechDraw
                HAS_FREECAD = True
                freecad_lib_path = path
                logger.info("Successfully imported FreeCAD, Import, and TechDraw!")
                return True
            except ImportError as e:
                logger.debug(f"Failed to import FreeCAD from {path}: {e}")
                continue

    logger.warning("FreeCAD was not found on the system path or import failed.")
    return False

# Trigger discovery
discover_freecad()

def is_svg_drawing_empty(svg_path):
    """
    Check if the exported FreeCAD TechDraw SVG page is empty (i.e. contains no actual drawing shapes in 'DrawingContent' group).
    This handles cases like 2D wireframe drawings where TechDraw HLR projects nothing.
    """
    if not os.path.exists(svg_path):
        return True
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        drawing_content_group = None
        for elem in root.iter():
            # Extract local name to handle XML namespaces
            local_name = elem.tag.split('}')[-1]
            if local_name == 'g' and elem.attrib.get('id') == 'DrawingContent':
                drawing_content_group = elem
                break
                
        if drawing_content_group is None:
            # If DrawingContent doesn't exist, assume not empty to avoid false alarms
            return False
            
        # Count graphic elements within DrawingContent recursively
        shapes = 0
        for child in drawing_content_group.iter():
            local_name = child.tag.split('}')[-1]
            if local_name in ('path', 'line', 'circle', 'rect', 'polygon', 'polyline', 'ellipse'):
                shapes += 1
                
        logger.info(f"Verified SVG drawing content: found {shapes} shapes inside 'DrawingContent'.")
        return shapes == 0
    except Exception as e:
        logger.error(f"Error checking SVG drawing emptiness: {e}")
        # On XML parsing error, return True to trigger fallback
        return True

def fit_and_scale_geometries(lines_group, circles_group, bolt_holes_group, target_center, max_size=60):
    """
    Fit and scale all lines, circles, and bolt holes uniformly inside a view bounding box.
    """
    pts = []
    for l in lines_group:
        pts.append(l["start"])
        pts.append(l["end"])
    for c in circles_group:
        cx, cy = c["center"]
        r = c["radius"]
        pts.append((cx - r, cy - r))
        pts.append((cx + r, cy + r))
    for bh in bolt_holes_group:
        cx, cy = bh["center"]
        r = bh["radius"]
        pts.append((cx - r, cy - r))
        pts.append((cx + r, cy + r))
        
    if not pts:
        return [], [], [], 0, 0
        
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    w_box = max_x - min_x
    h_box = max_y - min_y
    cx = min_x + w_box / 2
    cy = min_y + h_box / 2
    
    curr_max = max(w_box, h_box)
    scale = max_size / curr_max if curr_max > 0 else 1.0
    
    fitted_lines = []
    for l in lines_group:
        x1 = target_center[0] + (l["start"][0] - cx) * scale
        y1 = target_center[1] + (l["start"][1] - cy) * scale
        x2 = target_center[0] + (l["end"][0] - cx) * scale
        y2 = target_center[1] + (l["end"][1] - cy) * scale
        fitted_lines.append({
            "start": (x1, y1),
            "end": (x2, y2),
            "style": l["style"]
        })
        
    fitted_circles = []
    for c in circles_group:
        x = target_center[0] + (c["center"][0] - cx) * scale
        y = target_center[1] + (c["center"][1] - cy) * scale
        fitted_circles.append({
            "center": (x, y),
            "radius": c["radius"] * scale,
            "style": c["style"]
        })
        
    fitted_bolt_holes = []
    for bh in bolt_holes_group:
        x = target_center[0] + (bh["center"][0] - cx) * scale
        y = target_center[1] + (bh["center"][1] - cy) * scale
        fitted_bolt_holes.append({
            "center": (x, y),
            "radius": bh["radius"] * scale,
            "style": bh["style"]
        })
        
    return fitted_lines, fitted_circles, fitted_bolt_holes, w_box * scale, h_box * scale

def project_3d_cad_in_process(file_path, views):
    """
    Spawns a subprocess to project the 3D CAD model in console mode (headless)
    and loads the resulting geometry JSON metadata.
    This protects the parent process from C++ segfaults on corrupt files.
    """
    import subprocess
    import json
    
    logger.info(f"Isolated headless projection subprocess for {file_path}")
    
    # We will write temporary args.json and output paths
    out_dir = os.path.dirname(os.path.abspath(file_path))
    temp_out_base = os.path.join(out_dir, "headless_tmp")
    result_json_path = temp_out_base + "_result.json"
    
    # Clean up old temporary files if they exist
    if os.path.exists(result_json_path):
        try:
            os.remove(result_json_path)
        except Exception:
            pass
            
    args_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'freecad_args.json')
    config = {
        "input_file": os.path.abspath(file_path),
        "output_file": temp_out_base,
        "views": views
    }
    
    # Standard python executable running this script
    py_exec = sys.executable
    
    # If running inside Streamlit which uses custom FreeCAD resources
    # verify if a custom python is packaged with FreeCAD
    if sys.platform == "darwin":
        fc_py = "/Applications/FreeCAD.app/Contents/Resources/bin/python"
        if os.path.exists(fc_py):
            py_exec = fc_py
            
    projector_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freecad_projector_headless.py")
    
    cmd = [py_exec, projector_script]
    
    try:
        with open(args_path, 'w') as f:
            json.dump(config, f, indent=2)
            
        logger.info(f"Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        # Check result
        if res.returncode != 0 or not os.path.exists(result_json_path):
            raise RuntimeError(
                f"Subprocess projection failed (exit code: {res.returncode}). \n"
                f"Stdout: {res.stdout}\nStderr: {res.stderr}"
            )
            
        with open(result_json_path, 'r') as f_res:
            geometry_data = json.load(f_res)
            
        logger.info("Headless projection completed successfully!")
        return geometry_data
        
    finally:
        # Cleanup
        if os.path.exists(args_path):
            try:
                os.remove(args_path)
            except Exception:
                pass
        if os.path.exists(result_json_path):
            try:
                os.remove(result_json_path)
            except Exception:
                pass

def project_3d_cad(file_path, output_svg_path, views=None):
    """
    Project 3D views (top, front, side) of a STEP/IGS file to 2D SVG vector representation
    using native FreeCAD / OpenCascade / TechDraw topology projections.
    """
    if views is None:
        views = ['top', 'front', 'side']
        
    logger.info(f"Processing 3D CAD file: '{file_path}' (views: {views})")
    
    if not HAS_FREECAD:
        raise RuntimeError("FreeCAD / OpenCascade environment is not available on this system. Headless CAD projection failed.")
        
    return project_3d_cad_in_process(file_path, views)
