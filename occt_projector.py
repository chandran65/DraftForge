#!/usr/bin/env python3
"""
occt_projector.py — True OCCT Edge + Face Projection Engine

Supports 6 view directions and 5 render modes:
  Views:  initial (top-down), bottom, front, back, left, right
  Modes:  2d_wireframe, 3d_wireframe, 3d_hidden_lines,
          3d_flat_shading, 3d_smooth_shading
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
    env_path = os.environ.get("FREECAD_LIB_PATH")
    candidates = []
    if env_path:
        candidates.append(env_path)
    if sys.platform == "darwin":
        candidates += [
            "/Applications/FreeCAD.app/Contents/Resources/lib",
            "/Applications/FreeCAD.app/Contents/lib",
            "/opt/homebrew/lib",
        ]
    elif sys.platform.startswith("linux"):
        candidates += [
            "/usr/lib/freecad/lib",
            "/usr/lib/freecad-python3/lib",
            "/usr/lib/freecad-daily/lib",
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
            try:
                import FreeCAD  # noqa: F401
                return True
            except ImportError:
                continue
    return False


_discover_freecad()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DISC_POINTS   = 24     # edge discretisation density
TESS_PREC     = 0.3    # mm face tessellation accuracy

# Single view: centred on A4 landscape with room for title block
VIEW_CENTER  = (130, 92)
VIEW_MAX_DIM = 130      # mm — fills most of the sheet

VIEW_TITLES = {
    "initial": "TOP VIEW (INITIAL)",
    "bottom":  "BOTTOM VIEW",
    "front":   "FRONT VIEW",
    "back":    "BACK VIEW",
    "left":    "LEFT SIDE VIEW",
    "right":   "RIGHT SIDE VIEW",
}

# Camera direction: unit vector pointing FROM the camera TOWARD the scene
VIEW_CAM_DIR = {
    "initial": (0,  0, -1),  # above, looking down
    "bottom":  (0,  0,  1),  # below, looking up
    "front":   (0, -1,  0),  # front, looking back  (+Y into scene)
    "back":    (0,  1,  0),  # rear,  looking fwd   (-Y into scene)
    "left":    (-1, 0,  0),  # left,  looking right (+X into scene)
    "right":   (1,  0,  0),  # right, looking left  (-X into scene)
}

# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------
def _project_pt(p, view: str):
    """Project 3D FreeCAD Vector → 2D canvas (x, y).  +X=right, +Y=down."""
    if view == "initial":
        return ( p.x, -p.y)   # top-down: X→X, Y→-Y (flip so +Y goes up on canvas)
    elif view == "bottom":
        return ( p.x,  p.y)   # bottom-up: X→X, Y→Y (Y already down)
    elif view == "front":
        return ( p.x, -p.z)   # front: X→X, Z→-Z
    elif view == "back":
        return (-p.x, -p.z)   # back:  mirror X
    elif view == "left":
        return ( p.y, -p.z)   # left side: Y→X, Z→-Z
    elif view == "right":
        return (-p.y, -p.z)   # right side: -Y→X, Z→-Z
    else:
        return ( p.x, -p.z)


def _depth_pt(p, view: str) -> float:
    """Depth along view axis. Higher = closer to camera (drawn last in painter's sort)."""
    if view == "initial":  return  p.z
    elif view == "bottom": return -p.z
    elif view == "front":  return -p.y
    elif view == "back":   return  p.y
    elif view == "left":   return -p.x
    elif view == "right":  return  p.x
    else:                  return -p.y


# ---------------------------------------------------------------------------
# Edge processing
# ---------------------------------------------------------------------------
def _edges_to_data(edges, view: str, n: int = DISC_POINTS):
    """
    Returns list of (d_string, avg_depth) for every edge.
    d_string: SVG path 'd' attribute  →  'M x,y L x,y ...'
    avg_depth: mean depth along view axis (higher = closer to camera)
    """
    result = []
    for edge in edges:
        try:
            pts_3d = edge.discretize(n)
        except Exception:
            try:
                pts_3d = [v.Point for v in edge.Vertexes]
            except Exception:
                continue
        if len(pts_3d) < 2:
            continue
        pts_2d = [_project_pt(p, view) for p in pts_3d]
        avg_depth = sum(_depth_pt(p, view) for p in pts_3d) / len(pts_3d)
        d = f"M {pts_2d[0][0]:.4f},{pts_2d[0][1]:.4f}"
        for pt in pts_2d[1:]:
            d += f" L {pt[0]:.4f},{pt[1]:.4f}"
        result.append((d, float(avg_depth)))
    return result


# ---------------------------------------------------------------------------
# Face tessellation (for shading modes)
# ---------------------------------------------------------------------------
def _tessellate_faces(shape, view: str, precision: float = TESS_PREC):
    """
    Tessellate all Shape faces, project triangles to 2D, compute shading.
    Returns list of dicts: {pts_2d, intensity, depth, back_facing}
    """
    cam = VIEW_CAM_DIR.get(view, (0, -1, 0))

    # Key light: offset from camera so it's not flat-lit
    lx = -cam[0] * 0.3 + 0.5
    ly = -cam[1] * 0.3 - 0.4
    lz = -cam[2] * 0.5 + 0.7
    lmag = math.sqrt(lx * lx + ly * ly + lz * lz) + 1e-10
    lx /= lmag;  ly /= lmag;  lz /= lmag

    triangles = []
    for face in shape.Faces:
        try:
            pts_3d, tris = face.tessellate(precision)
        except Exception:
            continue
        for tri in tris:
            try:
                v0, v1, v2 = pts_3d[tri[0]], pts_3d[tri[1]], pts_3d[tri[2]]
            except IndexError:
                continue

            # Project to 2D canvas
            p0 = _project_pt(v0, view)
            p1 = _project_pt(v1, view)
            p2 = _project_pt(v2, view)

            # Triangle normal (cross product of edges in 3D)
            e1 = (v1.x - v0.x, v1.y - v0.y, v1.z - v0.z)
            e2 = (v2.x - v0.x, v2.y - v0.y, v2.z - v0.z)
            nx = e1[1] * e2[2] - e1[2] * e2[1]
            ny = e1[2] * e2[0] - e1[0] * e2[2]
            nz = e1[0] * e2[1] - e1[1] * e2[0]
            nmag = math.sqrt(nx * nx + ny * ny + nz * nz) + 1e-10
            nx /= nmag;  ny /= nmag;  nz /= nmag

            # Back-face test: dot(normal, cam_direction) > 0 → back-facing
            dot_cam = nx * cam[0] + ny * cam[1] + nz * cam[2]
            back_facing = dot_cam > 0.05

            # Diffuse lighting + ambient
            dot_light = nx * lx + ny * ly + nz * lz
            if back_facing:
                intensity = 0.12   # back face: very dark
            else:
                intensity = max(0.0, dot_light) * 0.75 + 0.25

            # Average depth for painter's algorithm
            depth = (
                _depth_pt(v0, view) + _depth_pt(v1, view) + _depth_pt(v2, view)
            ) / 3.0

            triangles.append({
                "pts":         [list(p0), list(p1), list(p2)],
                "intensity":   float(intensity),
                "depth":       float(depth),
                "back_facing": bool(back_facing),
            })

    # Painter's algorithm: draw far-away triangles first
    triangles.sort(key=lambda t: t["depth"])
    return triangles


# ---------------------------------------------------------------------------
# Hole Detection (circular edges facing the camera)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Hole Detection (circular edges facing the camera)
# ---------------------------------------------------------------------------
def fit_circle_2d(pts):
    n = len(pts)
    if n < 5:
        return None
    mean_u = sum(p[0] for p in pts) / n
    mean_v = sum(p[1] for p in pts) / n
    uu = [p[0] - mean_u for p in pts]
    vv = [p[1] - mean_v for p in pts]
    
    su = sum(uu); sv = sum(vv)
    su2 = sum(x*x for x in uu); sv2 = sum(y*y for y in vv); suv = sum(x*y for x, y in zip(uu, vv))
    su3 = sum(x*x*x for x in uu); sv3 = sum(y*y*y for y in vv)
    su2v = sum(x*x*y for x, y in zip(uu, vv)); suv2 = sum(x*y*y for x, y in zip(uu, vv))
    
    det = 4 * (su2 * sv2 - suv * suv)
    if abs(det) < 1e-9:
        return None
    A, B, D = 2 * su2, 2 * suv, su3 + suv2
    E, F, G = 2 * suv, 2 * sv2, su2v + sv3
    uc = (D * F - B * G) / det
    vc = (A * G - D * E) / det
    C = (su2 + sv2) / n
    R2 = C + uc**2 + vc**2
    if R2 < 0: return None
    R = math.sqrt(R2)
    center_u, center_v = uc + mean_u, vc + mean_v
    
    residuals = [math.sqrt((u - uc)**2 + (v - vc)**2) - R for u, v in zip(uu, vv)]
    mean_err = sum(residuals) / n
    variance = sum((r - mean_err)**2 for r in residuals) / n
    std_dev = math.sqrt(variance)
    return center_u, center_v, R, std_dev

def fit_circle_3d(pts_3d):
    n = len(pts_3d)
    if n < 5: return None
    mx = sum(p.x for p in pts_3d) / n
    my = sum(p.y for p in pts_3d) / n
    mz = sum(p.z for p in pts_3d) / n
    
    nx, ny, nz = 0.0, 0.0, 0.0
    for i in range(1, n - 1):
        v1x, v1y, v1z = pts_3d[i].x - mx, pts_3d[i].y - my, pts_3d[i].z - mz
        v2x, v2y, v2z = pts_3d[i+1].x - mx, pts_3d[i+1].y - my, pts_3d[i+1].z - mz
        cx, cy, cz = v1y * v2z - v1z * v2y, v1z * v2x - v1x * v2z, v1x * v2y - v1y * v2x
        nx += cx; ny += cy; nz += cz
    nmag = math.sqrt(nx*nx + ny*ny + nz*nz)
    if nmag < 1e-6: return None
    nx /= nmag; ny /= nmag; nz /= nmag
    
    ax, ay, az = (1.0, 0.0, 0.0) if abs(nx) < 0.9 else (0.0, 1.0, 0.0)
    dot = ax * nx + ay * ny + az * nz
    ux, uy, uz = ax - dot * nx, ay - dot * ny, az - dot * nz
    umag = math.sqrt(ux*ux + uy*uy + uz*uz)
    ux /= umag; uy /= umag; uz /= umag
    vx, vy, vz = ny * uz - nz * uy, nz * ux - nx * uz, nx * uy - ny * ux
    
    pts_2d = [( (p.x - mx)*ux + (p.y - my)*uy + (p.z - mz)*uz, (p.x - mx)*vx + (p.y - my)*vy + (p.z - mz)*vz ) for p in pts_3d]
    fit = fit_circle_2d(pts_2d)
    if fit is None: return None
    uc, vc, R, err = fit
    cx, cy, cz = mx + uc * ux + vc * vx, my + uc * uy + vc * vy, mz + uc * uz + vc * vz
    return cx, cy, cz, nx, ny, nz, R, err

def _detect_holes(edges, view_name, np_params):
    """
    Robust scan of edges using 3D circle fitting and arc grouping.
    Supports native circular edges, NURBS BSpline representations, 
    and split/segmented circular arcs.
    """
    cam = VIEW_CAM_DIR.get(view_name, (0, -1, 0))
    arcs = []
    
    for edge in edges:
        try:
            pts_3d = edge.discretize(24)
            fit = fit_circle_3d(pts_3d)
            if fit is None:
                continue
            cx, cy, cz, nx, ny, nz, R, err = fit
            if R < 0.05 or err / R > 0.008:
                continue
            
            # Check: circle must face the camera (axis ∥ cam direction)
            dot = abs(nx*cam[0] + ny*cam[1] + nz*cam[2])
            if dot < 0.85:
                continue             # circle is too tilted
                
            p0, p1 = pts_3d[0], pts_3d[-1]
            dist_ends = math.sqrt((p1.x - p0.x)**2 + (p1.y - p0.y)**2 + (p1.z - p0.z)**2)
            if dist_ends < 0.05:
                span_deg = 360.0
            else:
                chord = math.sqrt((p1.x - p0.x)**2 + (p1.y - p0.y)**2 + (p1.z - p0.z)**2)
                ratio = min(1.0, chord / (2 * R))
                span_deg = math.degrees(2 * math.asin(ratio))
                
            arcs.append({
                "center": (cx, cy, cz),
                "radius": R,
                "span": span_deg,
            })
        except Exception:
            pass

    if not arcs:
        return []

    # ---- Group arcs representing same circle at same depth ----------------
    from collections import defaultdict
    arc_groups = defaultdict(list)
    for arc in arcs:
        cx, cy, cz = arc["center"]
        key = (
            round(arc["radius"], 2),
            round(cx, 1),
            round(cy, 1),
            round(cz, 1),
        )
        arc_groups[key].append(arc)

    circles_3d = []
    for key, group in arc_groups.items():
        total_span = sum(a["span"] for a in group)
        if total_span >= 270.0:
            avg_cx = sum(a["center"][0] for a in group) / len(group)
            avg_cy = sum(a["center"][1] for a in group) / len(group)
            avg_cz = sum(a["center"][2] for a in group) / len(group)
            avg_r = sum(a["radius"] for a in group) / len(group)
            
            import FreeCAD
            center_vec = FreeCAD.Vector(avg_cx, avg_cy, avg_cz)
            center_2d = _project_pt(center_vec, view_name)
            depth_coord = _depth_pt(center_vec, view_name)
            
            circles_3d.append({
                "center_3d": [avg_cx, avg_cy, avg_cz],
                "radius": avg_r,
                "center_2d": list(center_2d),
                "depth_coord": depth_coord,
            })

    if not circles_3d:
        return []

    # ---- Group 3D circles by 2D projection (same hole) --------------------
    hole_groups = defaultdict(list)
    for c in circles_3d:
        cx_2d, cy_2d = c["center_2d"]
        key = (
            round(c["radius"], 2),
            round(cx_2d, 0),
            round(cy_2d, 0),
        )
        hole_groups[key].append(c)

    holes = []
    for key, group in hole_groups.items():
        group_s = sorted(group, key=lambda c: c["depth_coord"], reverse=True)
        rep = group_s[0]
        
        if len(group_s) > 1:
            depth = abs(group_s[0]["depth_coord"] - group_s[-1]["depth_coord"])
        else:
            depth = 0.0

        norm_cx, norm_cy = _norm_pt(
            rep["center_2d"][0], rep["center_2d"][1], *np_params
        )
        radius_norm = rep["radius"] * np_params[2]

        holes.append({
            "diameter":    round(rep["radius"] * 2,  3),
            "radius_norm": round(radius_norm, 3),
            "depth":       round(depth,       3),
            "center":      [round(norm_cx, 3), round(norm_cy, 3)],
            "center_3d":   rep["center_3d"],
            "label":       f"⌀{rep['radius']*2:.2f}",
        })

    holes.sort(key=lambda h: h["diameter"])
    for i, h in enumerate(holes):
        h["id"] = f"H{i+1}"

    print(f"[occt] Detected {len(holes)} holes using robust 3D fitting", flush=True)
    return holes


def _compute_bbox(svg_paths):
    xs, ys = [], []
    for d in svg_paths:
        cleaned = d.replace("M", " ").replace("L", " ").strip()
        for pair in cleaned.split():
            try:
                px, py = pair.split(",")
                xs.append(float(px));  ys.append(float(py))
            except ValueError:
                pass
    if not xs:
        return 0, 0, 1, 1
    return min(xs), min(ys), max(xs), max(ys)


def _get_norm_params(svg_paths, center, max_dim):
    """Return (cx_src, cy_src, scale, cx_dst, cy_dst)."""
    min_x, min_y, max_x, max_y = _compute_bbox(svg_paths)
    w = max_x - min_x
    h = max_y - min_y
    cx_src = min_x + w / 2
    cy_src = min_y + h / 2
    span = max(w, h, 1e-6)
    scale = max_dim / span
    cx_dst, cy_dst = center
    return cx_src, cy_src, scale, cx_dst, cy_dst


def _norm_pt(x, y, cx_src, cy_src, scale, cx_dst, cy_dst):
    return (cx_dst + (x - cx_src) * scale, cy_dst + (y - cy_src) * scale)


def _norm_paths(paths, *np):
    def rescale(d):
        tokens = d.split()
        out = []
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t in ("M", "L"):
                out.append(t); i += 1
            else:
                try:
                    rx, ry = t.split(",")
                    nx, ny = _norm_pt(float(rx), float(ry), *np)
                    out.append(f"{nx:.3f},{ny:.3f}")
                except Exception:
                    out.append(t)
                i += 1
        return " ".join(out)
    return [rescale(d) for d in paths]


def _norm_faces(faces, *np):
    result = []
    for f in faces:
        norm_pts = [list(_norm_pt(p[0], p[1], *np)) for p in f["pts"]]
        result.append({
            "pts":         norm_pts,
            "intensity":   f["intensity"],
            "depth":       f["depth"],
            "back_facing": f["back_facing"],
        })
    return result


# ---------------------------------------------------------------------------
# Main projection function
# ---------------------------------------------------------------------------
def project_iges_step(
    input_file: str,
    view_name: str = "front",
    render_mode: str = "2d_wireframe",
    disc_pts: int = DISC_POINTS,
):
    import FreeCAD  # noqa: F401
    import Part

    t0 = time.time()
    print(f"[occt] Loading: {input_file}", flush=True)
    print(f"[occt] View: {view_name}  |  Mode: {render_mode}", flush=True)

    # ---- Load shape --------------------------------------------------------
    shape = Part.read(input_file)
    if shape is None or shape.isNull():
        raise ValueError(f"Part.read() returned null shape: {input_file}")

    edges  = shape.Edges
    bbox   = shape.BoundBox
    model_w = bbox.XLength
    model_h = bbox.YLength
    model_d = bbox.ZLength

    print(
        f"[occt] {len(edges)} edges | {len(shape.Faces)} faces | "
        f"BBox {model_w:.2f}W × {model_d:.2f}D × {model_h:.2f}H mm",
        flush=True,
    )

    center  = VIEW_CENTER
    max_dim = VIEW_MAX_DIM

    # ---- Project edges -----------------------------------------------------
    edge_data  = _edges_to_data(edges, view_name, disc_pts)
    all_paths  = [d for d, _ in edge_data]
    all_depths = [dep for _, dep in edge_data]

    if not all_paths:
        raise ValueError("No projected edges for this view.")

    # ---- Normalization parameters (derived from all edges) -----------------
    np_params = _get_norm_params(all_paths, center, max_dim)

    # ---- Detect holes (circular edges facing this view) --------------------
    holes = _detect_holes(edges, view_name, np_params)

    bolt_holes = []
    for h in holes:
        bolt_holes.append({
            "center": h["center"],
            "radius": h["radius_norm"],
        })

    # ---- Classify edges for 3D wireframe / hidden lines --------------------
    visible_paths = []
    hidden_paths  = []

    if render_mode in ("3d_wireframe", "3d_hidden_lines") and all_depths:
        # Top-40% by depth = visible (closer to camera); bottom-60% = hidden
        sorted_d = sorted(all_depths)
        threshold = sorted_d[int(len(sorted_d) * 0.40)]
        vis_raw = [d for d, dep in edge_data if dep >= threshold]
        hid_raw = [d for d, dep in edge_data if dep <  threshold]
        visible_paths = _norm_paths(vis_raw, *np_params)
        hidden_paths  = _norm_paths(hid_raw, *np_params)
    else:
        visible_paths = _norm_paths(all_paths, *np_params)

    # ---- Tessellate faces (shading modes) ----------------------------------
    faces = []
    if render_mode in ("3d_flat_shading", "3d_smooth_shading"):
        print("[occt] Tessellating faces...", flush=True)
        raw_faces = _tessellate_faces(shape, view_name, TESS_PREC)
        faces = _norm_faces(raw_faces, *np_params)
        print(f"[occt] {len(faces)} triangles tessellated", flush=True)
        # For smooth shading, clear visible edges (faces speak for themselves)
        if render_mode == "3d_smooth_shading":
            visible_paths = []

    # ---- View extents for dimension lines ----------------------------------
    ref_paths = visible_paths + hidden_paths
    if ref_paths:
        bx_min, by_min, bx_max, by_max = _compute_bbox(ref_paths)
        vw = bx_max - bx_min
        vh = by_max - by_min
    else:
        vw = vh = max_dim * 0.8

    cx, cy = center
    dimensions = [
        {
            "start":  (cx - vw / 2,      cy + vh / 2 + 8),
            "end":    (cx + vw / 2,       cy + vh / 2 + 8),
            "text":   f"{model_w:.2f}",
            "offset": 0,
        },
        {
            "start":  (cx + vw / 2 + 8,  cy - vh / 2),
            "end":    (cx + vw / 2 + 8,  cy + vh / 2),
            "text":   f"{model_d:.2f}",
            "offset": 0,
        },
    ]

    elapsed = time.time() - t0
    print(f"[occt] Done in {elapsed:.2f}s — {len(visible_paths)} visible, {len(hidden_paths)} hidden, {len(faces)} faces", flush=True)

    return {
        "source":      "cad_occt_edge_projection",
        "file_name":   os.path.basename(input_file),
        "width":       297,
        "height":      210,
        "render_mode": render_mode,
        "views": {
            view_name: {
                "title":            VIEW_TITLES.get(view_name, view_name.upper() + " VIEW"),
                "center":           list(center),
                "svg_paths":        visible_paths,
                "hidden_svg_paths": hidden_paths,
                "faces":            faces,
                "lines":            [],
                "circles":          [],
                "bolt_holes":       bolt_holes,
                "holes":            holes,
                "dimensions":       dimensions,
            }
        },
        "meta": {
            "has_freecad": True,
            "part_type":   shape.ShapeType,
            "engine":      "OpenCascade / FreeCAD Part.read + Edge discretisation",
            "params": {
                "Overall Width":  f"{model_w:.2f} mm",
                "Overall Depth":  f"{model_d:.2f} mm",
                "Overall Height": f"{model_h:.2f} mm",
                "Total Edges":    str(len(edges)),
                "Total Faces":    str(len(shape.Faces)),
                "Shape Type":     shape.ShapeType,
                "View":           VIEW_TITLES.get(view_name, view_name),
                "Render Mode":    render_mode.replace("_", " ").title(),
            },
        },
    }


# ---------------------------------------------------------------------------
# Subprocess entry point
# ---------------------------------------------------------------------------
def main():
    args_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freecad_args.json")
    if not os.path.exists(args_path):
        print("[occt] ERROR: freecad_args.json not found.", file=sys.stderr)
        sys.exit(1)

    with open(args_path, "r") as f:
        config = json.load(f)

    input_file  = config.get("input_file")
    output_file = config.get("output_file")
    view_name   = config.get("view_name",   "front")
    render_mode = config.get("render_mode", "2d_wireframe")
    disc_pts    = config.get("disc_pts",    DISC_POINTS)

    if not input_file or not os.path.exists(input_file):
        print(f"[occt] ERROR: input_file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    try:
        gd = project_iges_step(input_file, view_name, render_mode, disc_pts)
    except Exception as e:
        import traceback
        print(f"[occt] FATAL: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    out_json = os.path.splitext(output_file)[0] + "_result.json"
    with open(out_json, "w") as f_out:
        json.dump(gd, f_out, indent=2)

    print(f"[occt] Result written to: {out_json}", flush=True)


if __name__ == "__main__":
    main()
