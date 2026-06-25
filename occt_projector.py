#!/usr/bin/env python3
"""
occt_projector.py — True OCCT Edge Projection Engine

Uses FreeCAD's Part module (OpenCascade Technology backend) to:
1. Load IGES/STEP files using Part.read() — gets all faces/edges/curves
2. Discretize every 3D edge into polyline points
3. Project to true orthographic 2D views (top, front, side, iso)
4. Emit structured geometry_data dict (lines + circles) for the renderer

This is a subprocess-safe script — designed to be called from cad_parser.py
via subprocess with a config JSON and write a result JSON.
"""

import os
import sys
import json
import math
import time

# ---------------------------------------------------------------------------
# Bootstrap FreeCAD lib path
# ---------------------------------------------------------------------------
def _discover_freecad():
    """Find and prepend the FreeCAD lib directory to sys.path."""
    env_path = os.environ.get("FREECAD_LIB_PATH")
    candidates = []
    if env_path:
        candidates.append(env_path)
    if sys.platform == "darwin":
        candidates += [
            "/Applications/FreeCAD.app/Contents/Resources/lib",
            "/Applications/FreeCAD.app/Contents/lib",
            "/opt/homebrew/lib",
            "/opt/homebrew/opt/freecad/lib",
        ]
    elif sys.platform.startswith("linux"):
        candidates += [
            "/usr/lib/freecad/lib",
            "/usr/lib/freecad-python3/lib",
            "/usr/lib/freecad-daily/lib",
            "/usr/share/freecad/lib",
        ]
    elif sys.platform == "win32":
        candidates += [
            r"C:\Program Files\FreeCAD\bin",
            r"C:\Program Files\FreeCAD\lib",
        ]

    for p in candidates:
        if os.path.isdir(p):
            if p not in sys.path:
                sys.path.insert(0, p)
            # Verify FreeCAD is importable from this path
            try:
                import FreeCAD  # noqa: F401
                return True
            except ImportError:
                continue
    return False


_discover_freecad()

# ---------------------------------------------------------------------------
# Projection utilities
# ---------------------------------------------------------------------------
# Discretisation density (points per edge).  Higher = smoother curves.
DISC_POINTS = 24


def _project_pt(p, view: str):
    """
    Project a 3D FreeCAD Vector to 2D (x, y) canvas coordinates.
    Convention: +X = right, +Y = down on canvas.
    """
    if view == "front":   # camera at -Y, looking +Y  →  canvas (X, -Z)
        return (p.x, -p.z)
    elif view == "top":   # camera at +Z, looking -Z  →  canvas (X, -Y)
        return (p.x, -p.y)
    elif view == "side":  # camera at +X, looking -X  →  canvas (-Y, -Z)
        return (-p.y, -p.z)
    elif view == "iso":   # standard isometric 30° projection
        a = math.radians(30)
        return (
            (p.x - p.y) * math.cos(a),
            -(p.x + p.y) * math.sin(a) - p.z,
        )
    else:
        return (p.x, -p.z)


def _discretize_edge(edge, view: str, n: int = DISC_POINTS):
    """
    Discretize a Part Edge into projected 2D polyline points.
    Returns list of (x, y) tuples.
    """
    try:
        pts_3d = edge.discretize(n)
    except Exception:
        # Fallback: use endpoint vertices only
        try:
            pts_3d = [v.Point for v in edge.Vertexes]
        except Exception:
            return []
    return [_project_pt(p, view) for p in pts_3d]


def _edges_to_svg_paths(edges, view: str, n: int = DISC_POINTS):
    """
    Convert a list of Part Edges to SVG <path d="..."> strings.
    Returns a list of 'd' attribute strings.
    """
    paths = []
    for edge in edges:
        pts = _discretize_edge(edge, view, n)
        if len(pts) < 2:
            continue
        d = f"M {pts[0][0]:.4f},{pts[0][1]:.4f}"
        for pt in pts[1:]:
            d += f" L {pt[0]:.4f},{pt[1]:.4f}"
        paths.append(d)
    return paths


def _compute_bbox(svg_paths):
    """Return (min_x, min_y, max_x, max_y) from a list of SVG path d strings.

    Each path uses the format: 'M x,y L x,y L x,y ...'
    Coordinates are comma-separated pairs separated by spaces after command letters.
    """
    xs, ys = [], []
    for d in svg_paths:
        # Strip command letters, then split on spaces/commas
        cleaned = d.replace("M", " ").replace("L", " ").strip()
        # Each coordinate pair is 'x,y'
        for pair in cleaned.split():
            try:
                parts = pair.split(",")
                if len(parts) == 2:
                    xs.append(float(parts[0]))
                    ys.append(float(parts[1]))
            except ValueError:
                pass
    if not xs:
        return 0, 0, 1, 1
    return min(xs), min(ys), max(xs), max(ys)


def _normalize_paths(svg_paths, center, max_dim=70):
    """
    Fit all SVG paths into a box of `max_dim` mm centred at `center`.
    Returns list of rescaled path d strings.
    """
    if not svg_paths:
        return []

    min_x, min_y, max_x, max_y = _compute_bbox(svg_paths)
    w = max_x - min_x
    h = max_y - min_y
    cx_src = min_x + w / 2
    cy_src = min_y + h / 2
    span = max(w, h, 1e-6)
    scale = max_dim / span

    cx_dst, cy_dst = center

    def rescale(d: str) -> str:
        tokens = d.split()
        out = []
        cmd = None
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t in ("M", "L"):
                cmd = t
                out.append(t)
                i += 1
            else:
                try:
                    raw_x, raw_y = t.split(",")
                    rx = float(raw_x)
                    ry = float(raw_y)
                    nx = cx_dst + (rx - cx_src) * scale
                    ny = cy_dst + (ry - cy_src) * scale
                    out.append(f"{nx:.3f},{ny:.3f}")
                except Exception:
                    out.append(t)
                i += 1
        return " ".join(out)

    return [rescale(d) for d in svg_paths]


# ---------------------------------------------------------------------------
# View layout constants (A4 Landscape: 297 × 210 mm)
# Layout: top-left = TOP, bottom-left = FRONT, top-right = ISO, bottom-right = SIDE
# ---------------------------------------------------------------------------
VIEW_CENTERS = {
    "top":   (80,  75),    # upper-left quadrant
    "front": (80, 165),    # lower-left quadrant
    "side":  (195, 165),   # lower-right quadrant
    "iso":   (195,  75),   # upper-right quadrant
}
VIEW_MAX_DIM = {
    "top":   75,
    "front": 65,
    "side":  65,
    "iso":   70,
}
VIEW_TITLES = {
    "top":   "TOP VIEW",
    "front": "FRONT VIEW",
    "side":  "RIGHT SIDE VIEW",
    "iso":   "ISOMETRIC VIEW",
}


# ---------------------------------------------------------------------------
# Main projection function
# ---------------------------------------------------------------------------
def project_iges_step(input_file: str, views=None, disc_pts: int = DISC_POINTS):
    """
    Load an IGES or STEP file and project all edges to 2D SVG path data
    for each requested view.

    Returns geometry_data dict compatible with DraftForge renderer.
    """
    if views is None:
        views = ["top", "front", "side"]

    import FreeCAD
    import Part

    t_start = time.time()
    print(f"[occt_projector] Loading: {input_file}", flush=True)

    # ---- Load shape --------------------------------------------------------
    shape = Part.read(input_file)
    if shape is None or shape.isNull():
        raise ValueError(f"Part.read() returned empty/null shape for: {input_file}")

    edges = shape.Edges
    if not edges:
        raise ValueError("No edges found in shape after loading.")

    bbox = shape.BoundBox
    model_w = bbox.XLength
    model_h = bbox.YLength
    model_d = bbox.ZLength

    print(
        f"[occt_projector] Loaded {len(edges)} edges | "
        f"Faces: {len(shape.Faces)} | "
        f"BBox: {model_w:.2f}W × {model_d:.2f}D × {model_h:.2f}H mm",
        flush=True,
    )

    # ---- Build geometry_data -----------------------------------------------
    geometry_data = {
        "source": "cad_occt_edge_projection",
        "file_name": os.path.basename(input_file),
        "width": 297,
        "height": 210,
        "views": {},
        "meta": {
            "has_freecad": True,
            "part_type": shape.ShapeType,
            "engine": "OpenCascade / FreeCAD Part.read + Edge discretisation",
            "params": {
                "Overall Width":   f"{model_w:.2f} mm",
                "Overall Depth":   f"{model_d:.2f} mm",
                "Overall Height":  f"{model_h:.2f} mm",
                "Total Edges":     str(len(edges)),
                "Total Faces":     str(len(shape.Faces)),
                "Shape Type":      shape.ShapeType,
            },
        },
    }

    # ---- Project each view -------------------------------------------------
    for view_name in views:
        if view_name not in VIEW_CENTERS:
            print(f"[occt_projector] Unknown view '{view_name}', skipping.", flush=True)
            continue

        center = VIEW_CENTERS[view_name]
        max_dim = VIEW_MAX_DIM[view_name]

        t_view = time.time()
        raw_paths = _edges_to_svg_paths(edges, view_name, disc_pts)
        norm_paths = _normalize_paths(raw_paths, center, max_dim)
        elapsed_view = time.time() - t_view

        print(
            f"[occt_projector] View '{view_name}': {len(norm_paths)} paths in {elapsed_view:.2f}s",
            flush=True,
        )

        # Compute view extents for dimension annotation
        if norm_paths:
            bx_min, by_min, bx_max, by_max = _compute_bbox(norm_paths)
            view_w = bx_max - bx_min
            view_h = by_max - by_min
        else:
            view_w = max_dim
            view_h = max_dim

        # Build dimension annotations
        cx, cy = center
        dimensions = []
        if view_name == "front":
            dimensions = [
                {
                    "start": (cx - view_w / 2, cy + view_h / 2 + 10),
                    "end":   (cx + view_w / 2, cy + view_h / 2 + 10),
                    "text":  f"{model_w:.2f}",
                    "offset": 0,
                },
                {
                    "start": (cx + view_w / 2 + 10, cy - view_h / 2),
                    "end":   (cx + view_w / 2 + 10, cy + view_h / 2),
                    "text":  f"{model_d:.2f}",
                    "offset": 0,
                },
            ]
        elif view_name == "top":
            dimensions = [
                {
                    "start": (cx - view_w / 2, cy - view_h / 2 - 10),
                    "end":   (cx + view_w / 2, cy - view_h / 2 - 10),
                    "text":  f"{model_w:.2f}",
                    "offset": 0,
                },
                {
                    "start": (cx + view_w / 2 + 10, cy - view_h / 2),
                    "end":   (cx + view_w / 2 + 10, cy + view_h / 2),
                    "text":  f"{model_h:.2f}",
                    "offset": 0,
                },
            ]
        elif view_name == "side":
            dimensions = [
                {
                    "start": (cx - view_w / 2, cy + view_h / 2 + 10),
                    "end":   (cx + view_w / 2, cy + view_h / 2 + 10),
                    "text":  f"{model_h:.2f}",
                    "offset": 0,
                },
                {
                    "start": (cx + view_w / 2 + 10, cy - view_h / 2),
                    "end":   (cx + view_w / 2 + 10, cy + view_h / 2),
                    "text":  f"{model_d:.2f}",
                    "offset": 0,
                },
            ]

        geometry_data["views"][view_name] = {
            "title": VIEW_TITLES[view_name],
            "center": center,
            "svg_paths": norm_paths,   # raw SVG path d strings (full fidelity)
            "lines": [],               # populated by renderer from svg_paths
            "circles": [],
            "bolt_holes": [],
            "dimensions": dimensions,
        }

    t_total = time.time() - t_start
    print(f"[occt_projector] Done in {t_total:.2f}s total", flush=True)
    return geometry_data


# ---------------------------------------------------------------------------
# Subprocess entry point (called from cad_parser.py)
# ---------------------------------------------------------------------------
def main():
    args_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freecad_args.json")
    if not os.path.exists(args_path):
        print("[occt_projector] ERROR: freecad_args.json not found.", file=sys.stderr)
        sys.exit(1)

    with open(args_path, "r") as f:
        config = json.load(f)

    input_file = config.get("input_file")
    output_file = config.get("output_file")
    views = config.get("views", ["top", "front", "side"])
    disc_pts = config.get("disc_pts", DISC_POINTS)

    if not input_file or not os.path.exists(input_file):
        print(f"[occt_projector] ERROR: input_file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    try:
        geometry_data = project_iges_step(input_file, views=views, disc_pts=disc_pts)
    except Exception as e:
        print(f"[occt_projector] FATAL: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    # Write result JSON
    out_json = os.path.splitext(output_file)[0] + "_result.json"
    with open(out_json, "w") as f_out:
        json.dump(geometry_data, f_out, indent=2)

    print(f"[occt_projector] Result written to: {out_json}", flush=True)


if __name__ == "__main__":
    main()
