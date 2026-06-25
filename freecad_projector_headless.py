import os
import sys
import json
import math

# Discover and append FreeCAD lib path to sys.path
def discover_freecad():
    env_path = os.environ.get("FREECAD_LIB_PATH")
    paths_to_check = []
    if env_path:
        paths_to_check.append(env_path)
    if sys.platform == "darwin":
        paths_to_check.extend([
            "/Applications/FreeCAD.app/Contents/Resources/lib",
            "/Applications/FreeCAD.app/Contents/lib",
            "/opt/homebrew/lib",
            "/opt/homebrew/opt/freecad/lib"
        ])
    elif sys.platform.startswith("linux"):
        paths_to_check.extend([
            "/usr/lib/freecad/lib",
            "/usr/lib/freecad-python3/lib",
            "/usr/lib/freecad-daily/lib",
            "/usr/share/freecad/lib"
        ])
    elif sys.platform == "win32":
        paths_to_check.extend([
            r"C:\Program Files\FreeCAD\bin",
            r"C:\Program Files\FreeCAD\lib",
            r"C:\Program Files (x86)\FreeCAD\bin"
        ])
    for path in paths_to_check:
        if os.path.exists(path):
            if path not in sys.path:
                sys.path.append(path)
            return True
    return False

discover_freecad()

# Import FreeCAD modules
import FreeCAD
import Part
import TechDraw
import Import

# Fit and scale geometries helper
def fit_and_scale_geometries(lines_group, circles_group, bolt_holes_group, target_center, max_size=60):
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


def main():
    args_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'freecad_args.json')
    if not os.path.exists(args_path):
        sys.exit(1)
        
    with open(args_path, 'r') as f:
        config = json.load(f)
        
    input_file = config.get('input_file')
    output_file = config.get('output_file')
    views = config.get('views', ['top', 'front', 'side'])
    
    doc = FreeCAD.newDocument("HeadlessProjectionDoc")
    try:
        try:
            Import.insert(input_file, doc.Name)
        except Exception as e:
            print("Import.insert failed:", e)
        
        shapes = []
        for obj in doc.Objects:
            if hasattr(obj, 'Shape') and obj.Shape is not None and not obj.Shape.isNull():
                shapes.append(obj.Shape)
                
        if not shapes:
            print("No shapes found in doc via Import.insert. Falling back to Part.read...")
            try:
                shape = Part.read(input_file)
                if shape is not None and not shape.isNull():
                    obj = doc.addObject("Part::Feature", "ImportedShape")
                    obj.Shape = shape
                    shapes.append(obj.Shape)
            except Exception as e:
                print("Part.read failed:", e)
                
        if not shapes:
            raise ValueError("No valid 3D shapes found.")
            
        max_diagonal = 0.0
        for s in shapes:
            diag = s.BoundBox.DiagonalLength
            if diag > max_diagonal:
                max_diagonal = diag
                
        filtered_shapes = []
        for s in shapes:
            if s.BoundBox.DiagonalLength >= max_diagonal * 0.05:
                filtered_shapes.append(s)
                
        if not filtered_shapes:
            filtered_shapes = shapes
            
        compound_shape = Part.makeCompound(filtered_shapes)
        
        bbox = compound_shape.BoundBox
        model_w = bbox.XLength
        model_h = bbox.YLength
        model_d = bbox.ZLength
        
        geometry_data = {
            "source": "cad_freecad_headless",
            "file_name": os.path.basename(input_file),
            "views": {},
            "width": 297,
            "height": 210,
            "meta": {
                "has_freecad": True,
                "part_type": "3D Solid",
                "params": {
                    "Overall Width": f"{model_w:.2f} mm",
                    "Overall Height": f"{model_h:.2f} mm",
                    "Overall Depth": f"{model_d:.2f} mm",
                    "Total Components": f"{len(shapes)}",
                    "Visible Components": f"{len(filtered_shapes)}"
                }
            }
        }
        
        view_centers = {
            'top': (80, 65),
            'front': (80, 145),
            'side': (180, 145),
            'iso': (180, 65)
        }
        
        direction_map = {
            'top': FreeCAD.Vector(0, 0, 1),
            'front': FreeCAD.Vector(0, -1, 0),
            'side': FreeCAD.Vector(1, 0, 0),
            'iso': FreeCAD.Vector(1, -1, 1)
        }
        
        # Setup TechDraw Page and Template
        page = doc.addObject("TechDraw::DrawPage", "Page")
        template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
        template_paths = [
            os.path.join(FreeCAD.getHomePath(), "share", "Mod", "TechDraw", "Templates", "ISO", "A4_Landscape_TD.svg"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "TechDraw", "Templates", "A4_Landscape_TD.svg"),
            "/Applications/FreeCAD.app/Contents/Resources/share/Mod/TechDraw/Templates/ISO/A4_Landscape_TD.svg"
        ]
        template_path = None
        for p in template_paths:
            if os.path.exists(p):
                template_path = p
                break
        if template_path:
            template.Template = template_path
            page.Template = template
            
        import xml.etree.ElementTree as ET
        import re

        def parse_techdraw_view_svg(svg_data):
            lines_group = []
            wrapped_xml = f"<svg xmlns=\"http://www.w3.org/2000/svg\">{svg_data}</svg>"
            try:
                root = ET.fromstring(wrapped_xml)
            except Exception as e:
                print("XML parsing failed:", e)
                return lines_group
                
            for g in root.findall('.//g'):
                stroke_width_str = g.attrib.get('stroke-width', '0.7')
                try:
                    stroke_width = float(stroke_width_str)
                except ValueError:
                    stroke_width = 0.7
                    
                # standard engineering styles
                if stroke_width >= 0.5:
                    style = "visible"
                else:
                    style = "hidden"
                    
                for path in g.findall('.//path'):
                    d = path.attrib.get('d', '')
                    tokens = re.findall(r'[a-zA-Z]|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', d)
                    
                    current_pt = None
                    i = 0
                    while i < len(tokens):
                        token = tokens[i]
                        if token in ('M', 'm'):
                            try:
                                x = float(tokens[i+1])
                                y = float(tokens[i+2])
                                current_pt = (x, y)
                            except (IndexError, ValueError):
                                pass
                            i += 3
                        elif token in ('L', 'l'):
                            try:
                                x = float(tokens[i+1])
                                y = float(tokens[i+2])
                                next_pt = (x, y)
                                if current_pt:
                                    lines_group.append({
                                        "start": current_pt,
                                        "end": next_pt,
                                        "style": style
                                    })
                                current_pt = next_pt
                            except (IndexError, ValueError):
                                pass
                            i += 3
                        else:
                            i += 1
            return lines_group

        imported_features = [obj for obj in doc.Objects if hasattr(obj, 'Shape') and obj.Shape is not None]

        for view_name in views:
            if view_name not in direction_map:
                continue
                
            center = view_centers[view_name]
            dir_vec = direction_map[view_name]
            
            # Create proper DrawViewPart
            view = doc.addObject("TechDraw::DrawViewPart", f"View_{view_name}")
            view.Source = imported_features
            view.Direction = dir_vec
            view.HardHidden = True
            view.SmoothVisible = True
            page.addView(view)
            
            doc.recompute()
            
            svg_data = ""
            try:
                svg_data = TechDraw.viewPartAsSvg(view)
            except Exception as e:
                print(f"Error getting SVG for view {view_name}: {e}")
                
            # If empty or HLR returned no lines (common with open shells/surfaces), toggle CoarseView
            if not svg_data or len(svg_data.strip()) <= 150:
                print(f"View {view_name} empty under HLR. Retrying with CoarseView=True...")
                view.CoarseView = True
                doc.recompute()
                try:
                    svg_data = TechDraw.viewPartAsSvg(view)
                except Exception as e:
                    print(f"Error getting CoarseView SVG for view {view_name}: {e}")
                    
            if not svg_data:
                raise ValueError(f"Failed to project and export view {view_name} to SVG.")
                
            # Parse SVG geometry
            lines_group = parse_techdraw_view_svg(svg_data)
            
            max_size = 40 if view_name == 'side' else (50 if view_name in ('top', 'iso') else 60)
            
            fitted_lines, _, _, w_fit, h_fit = fit_and_scale_geometries(
                lines_group, [], [], center, max_size
            )
            
            title_map = {
                'top': 'TOP VIEW (SECTIONAL)',
                'front': 'FRONT VIEW (ORTHOGRAPHIC)',
                'side': 'SIDE VIEW (PROFILE)',
                'iso': 'ISOMETRIC VIEW (3D)'
            }
            
            dim_w = f"{model_w:.2f}"
            dim_h = f"{model_h:.2f}"
            dim_d = f"{model_d:.2f}"
            
            dimensions = []
            if view_name == 'top':
                dimensions = [
                    {"start": (center[0] - w_fit/2, center[1] + h_fit/2 + 10), "end": (center[0] + w_fit/2, center[1] + h_fit/2 + 10), "text": dim_w, "offset": 0},
                    {"start": (center[0] + w_fit/2 + 10, center[1] - h_fit/2), "end": (center[0] + w_fit/2 + 10, center[1] + h_fit/2), "text": dim_h, "offset": 0}
                ]
            elif view_name == 'front':
                dimensions = [
                    {"start": (center[0] - w_fit/2, center[1] + h_fit/2 + 12), "end": (center[0] + w_fit/2, center[1] + h_fit/2 + 12), "text": dim_w, "offset": 0},
                    {"start": (center[0] + w_fit/2 + 12, center[1] - h_fit/2), "end": (center[0] + w_fit/2 + 12, center[1] + h_fit/2), "text": dim_d, "offset": 0}
                ]
            elif view_name == 'side':
                dimensions = [
                    {"start": (center[0] - w_fit/2, center[1] - h_fit/2 - 10), "end": (center[0] + w_fit/2, center[1] - h_fit/2 - 10), "text": f"{dim_h} (DEPTH)", "offset": 0}
                ]
                
            geometry_data["views"][view_name] = {
                "title": title_map[view_name],
                "center": center,
                "lines": fitted_lines,
                "circles": [],
                "bolt_holes": [],
                "dimensions": dimensions
            }
            
        # Write output to json
        out_json_path = os.path.splitext(output_file)[0] + "_result.json"
        with open(out_json_path, 'w') as f_out:
            json.dump(geometry_data, f_out, indent=2)
            
    finally:
        FreeCAD.closeDocument("HeadlessProjectionDoc")

if __name__ == '__main__':
    main()
