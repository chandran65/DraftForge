import os
import math
import logging
from datetime import datetime

logger = logging.getLogger("3d2d_pipeline.renderer")

# Dynamic import helpers for cairosvg / reportlab
HAS_CAIROSVG = False
try:
    import cairosvg
    HAS_CAIROSVG = True
except ImportError:
    logger.debug("cairosvg not installed. Will use reportlab fallback for SVG->PDF conversion.")

HAS_REPORTLAB = False
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    HAS_REPORTLAB = True
except ImportError:
    logger.warning("reportlab not installed. PDF output compilation might be skipped.")

# Design Themes
THEMES = {
    "dark": {
        "bg": "#0A0F1D",         # Deep obsidian navy
        "grid": "#151F32",       # Subtle blueprint grid
        "border": "#2E3B52",     # Premium metallic border
        "title_bg": "#111827",   # Dark title block background
        "title_text": "#94A3B8", # Sleek slate text
        "visible": "#38BDF8",    # Electric ice blue (thick visible edges)
        "hidden": "#4B5563",     # Muted gray dashed (internal bores)
        "center": "#F59E0B",     # Warning amber centerlines (dash-dot)
        "bolt": "#E11D48",       # Crimson bolt holes
        "dimension": "#34D399",  # Emerald dimension markers
        "text": "#F8FAFC",       # High contrast arctic white
    },
    "light": {
        "bg": "#FFFFFF",         # Pure white drawing sheet
        "grid": "#F8FAFC",       # Extremely subtle drafting grid
        "border": "#000000",     # Crisp black border
        "title_bg": "#FFFFFF",   # Clean title block
        "title_text": "#000000", # Solid black title block text
        "visible": "#000000",    # Deep black visible outlines
        "hidden": "#64748B",     # Muted charcoal dashed lines
        "center": "#94A3B8",     # Subdued gray axis centerlines (or red #EF4444 if preferred, let's keep it classic black/slate)
        "bolt": "#000000",       # Black bolt holes
        "dimension": "#000000",  # Crisp black dimensions
        "text": "#000000",       # Clean black text
    }
}

def render_pipeline_output(geometry_data, output_base_path, theme_name="dark"):
    """
    Renders the unified geometry dictionary to a premium SVG and compiles it into a PDF.
    Supports geometry parsed from both CAD files (Path A) and drawings (Path B).
    """
    theme = THEMES.get(theme_name, THEMES["dark"])
    svg_path = f"{output_base_path}.svg"
    pdf_path = f"{output_base_path}.pdf"
    
    if geometry_data.get("source") == "cad_freecad":
        logger.info("Found native FreeCAD geometry. Keeping already generated SVG & PDF outputs.")
        png_path = f"{output_base_path}.png"
        try:
            import pypdfium2 as pdfium
            logger.info(f"Natively rendering high-resolution PNG using pypdfium2 from {pdf_path}...")
            doc = pdfium.PdfDocument(pdf_path)
            page = doc[0]
            bitmap = page.render(scale=5)
            pil_img = bitmap.to_pil()
            pil_img.save(png_path, "PNG")
            logger.info(f"PNG drawing successfully compiled at: {png_path}")
        except Exception as png_err:
            logger.warning(f"Optional PNG compilation skipped: {png_err}")
        return svg_path, pdf_path

    logger.info(f"Rendering vector drawing. Theme: '{theme_name}' -> '{svg_path}'")
    
    try:
        import svgwrite
    except ImportError:
        logger.error("svgwrite is required to run the renderer. Please run pip install -r requirements.txt")
        raise
        
    # Standard sheet sizes in mm
    width_mm = geometry_data.get("width", 297)
    height_mm = geometry_data.get("height", 210)
    
    dwg = svgwrite.Drawing(svg_path, size=(f"{width_mm}mm", f"{height_mm}mm"), viewBox=f"0 0 {width_mm} {height_mm}")
    
    # 1. Background Fill
    dwg.add(dwg.rect(insert=(0, 0), size=(width_mm, height_mm), fill=theme["bg"]))
    
    # 2. Subtle Drafting Grid
    grid_spacing = 10  # 10mm grid lines
    grid_group = dwg.g(id="grid-layer", stroke=theme["grid"], stroke_width=0.1)
    for x in range(0, int(width_mm), grid_spacing):
        grid_group.add(dwg.line(start=(x, 0), end=(x, height_mm)))
    for y in range(0, int(height_mm), grid_spacing):
        grid_group.add(dwg.line(start=(0, y), end=(width_mm, y)))
    dwg.add(grid_group)
    
    # 3. Outer Border Frame (Standard margins = 10mm)
    margin = 10
    dwg.add(dwg.rect(
        insert=(margin, margin),
        size=(width_mm - 2*margin, height_mm - 2*margin),
        fill="none",
        stroke=theme["border"],
        stroke_width=0.8,
        id="border-frame"
    ))
    
    # 4. Standard ISO Engineering Title Block (Bottom-Right Corner)
    # Block dimensions: 110mm x 35mm
    tb_w, tb_h = 110, 30
    tb_x = width_mm - margin - tb_w
    tb_y = height_mm - margin - tb_h
    
    title_block = dwg.g(id="title-block")
    title_block.add(dwg.rect(insert=(tb_x, tb_y), size=(tb_w, tb_h), fill=theme["title_bg"], stroke=theme["border"], stroke_width=0.5))
    
    # Horizontal partition lines
    title_block.add(dwg.line(start=(tb_x, tb_y + 10), end=(tb_x + tb_w, tb_y + 10), stroke=theme["border"], stroke_width=0.3))
    title_block.add(dwg.line(start=(tb_x, tb_y + 20), end=(tb_x + tb_w, tb_y + 20), stroke=theme["border"], stroke_width=0.3))
    # Vertical partition line
    title_block.add(dwg.line(start=(tb_x + 60, tb_y + 10), end=(tb_x + 60, tb_y + 30), stroke=theme["border"], stroke_width=0.3))
    
    # Text annotations inside Title Block
    title_block.add(dwg.text("DRAFTFORGE", insert=(tb_x + 5, tb_y + 7), font_size=3.5, font_weight="bold", fill=theme["text"], font_family="Inter, Roboto, sans-serif"))
    
    file_name = geometry_data.get("file_name", "UNKNOWN_SOURCE")
    title_block.add(dwg.text(f"FILE: {file_name[:28]}", insert=(tb_x + 5, tb_y + 16), font_size=2.8, fill=theme["title_text"], font_family="monospace"))
    title_block.add(dwg.text(f"DATE: {datetime.now().strftime('%Y-%m-%d')}", insert=(tb_x + 5, tb_y + 26), font_size=2.8, fill=theme["title_text"], font_family="monospace"))
    
    source_type = geometry_data.get("source", "UNKNOWN").upper()
    title_block.add(dwg.text(f"SRC: {source_type}", insert=(tb_x + 65, tb_y + 16), font_size=2.8, fill=theme["title_text"], font_family="Inter, sans-serif"))
    title_block.add(dwg.text("SCALE: 1:1  [A4]", insert=(tb_x + 65, tb_y + 26), font_size=2.8, fill=theme["title_text"], font_family="Inter, sans-serif"))
    
    dwg.add(title_block)
    
    # 5. Render Geometry Objects
    # If the source is CAD (has views) vs single-drawing raster/vector PDF
    if "views" in geometry_data:
        # Multi-view rendering
        for view_name, view in geometry_data["views"].items():
            # Create a group for the view
            view_group = dwg.g(id=f"view-{view_name}")
            
            # View titles
            title_pos = (view["center"][0], view["center"][1] - 35)
            view_group.add(dwg.text(view["title"], insert=title_pos, font_size=4.0, fill=theme["text"], font_weight="bold", text_anchor="middle", font_family="Inter, sans-serif"))
            
            # Draw lines
            for line in view.get("lines", []):
                style = line.get("style", "visible")
                stroke_color = theme[style]
                stroke_w = 0.5 if style == "visible" else 0.25
                dasharray = [3, 2] if style == "hidden" else ([6, 3, 1, 3] if style == "center" else None)
                
                line_kwargs = {
                    "start": line["start"],
                    "end": line["end"],
                    "stroke": stroke_color,
                    "stroke_width": stroke_w
                }
                if dasharray:
                    line_kwargs["stroke_dasharray"] = dasharray
                view_group.add(dwg.line(**line_kwargs))
                
            # Draw circles
            for circle in view.get("circles", []):
                style = circle.get("style", "visible")
                stroke_color = theme[style]
                stroke_w = 0.5 if style == "visible" else 0.25
                dasharray = [6, 3, 1, 3] if style == "center" else None
                
                circle_kwargs = {
                    "center": circle["center"],
                    "r": circle["radius"],
                    "fill": "none",
                    "stroke": stroke_color,
                    "stroke_width": stroke_w
                }
                if dasharray:
                    circle_kwargs["stroke_dasharray"] = dasharray
                view_group.add(dwg.circle(**circle_kwargs))
                
            # Draw bolt holes (Path A specialized)
            for hole in view.get("bolt_holes", []):
                view_group.add(dwg.circle(
                    center=hole["center"],
                    r=hole["radius"],
                    fill="none",
                    stroke=theme["bolt"],
                    stroke_width=0.4
                ))
                # Add crosshairs for bolt holes
                hc = hole["center"]
                hr = hole["radius"]
                view_group.add(dwg.line(start=(hc[0] - hr - 2, hc[1]), end=(hc[0] + hr + 2, hc[1]), stroke=theme["center"], stroke_width=0.15))
                view_group.add(dwg.line(start=(hc[0], hc[1] - hr - 2), end=(hc[0], hc[1] + hr + 2), stroke=theme["center"], stroke_width=0.15))
                
            # Draw dimensions
            for dim in view.get("dimensions", []):
                draw_dimension_callout(dwg, view_group, dim, theme)
                
            dwg.add(view_group)
            
    else:
        # Drawing mode (single layout)
        drawing_group = dwg.g(id="blueprint-drawing")
        
        # Scale factor if incoming canvas is larger than A4 limits
        in_w, in_h = geometry_data.get("width", 842), geometry_data.get("height", 595)
        # Leave margins of 15mm
        avail_w = width_mm - 30
        avail_h = height_mm - 30
        scale = min(avail_w / in_w, avail_h / in_h)
        
        # Centering offset
        dx = 15 + (avail_w - in_w * scale) / 2
        dy = 15 + (avail_h - in_h * scale) / 2
        
        logger.debug(f"Scaling canvas factor: {scale:.4f}, offsets: dx={dx}, dy={dy}")
        
        # Apply transformation matrix to group
        drawing_group.matrix(scale, 0, 0, scale, dx, dy)
        
        # Draw lines
        for line in geometry_data.get("lines", []):
            style = line.get("style", "visible")
            stroke_color = theme[style]
            stroke_w = 1.0 if style == "visible" else 0.5
            dasharray = [4, 3] if style == "hidden" else ([10, 5, 2, 5] if style == "center" else None)
            
            line_kwargs = {
                "start": line["start"],
                "end": line["end"],
                "stroke": stroke_color,
                "stroke_width": stroke_w / scale  # keep stroke scaling uniform
            }
            if dasharray:
                line_kwargs["stroke_dasharray"] = dasharray
            drawing_group.add(dwg.line(**line_kwargs))
            
        # Draw rectangles
        for rect in geometry_data.get("rects", []):
            drawing_group.add(dwg.rect(
                insert=(rect["x"], rect["y"]),
                size=(rect["w"], rect["h"]),
                fill="none",
                stroke=theme["visible"],
                stroke_width=1.0 / scale
            ))
            
        # Draw extracted texts
        for text in geometry_data.get("texts", []):
            drawing_group.add(dwg.text(
                text["text"],
                insert=text["position"],
                font_size=8.0 / scale,
                fill=theme["text"],
                font_family="monospace"
            ))
            
        dwg.add(drawing_group)
        
    # Save SVG
    dwg.save()
    logger.info(f"SVG blueprint file created at {svg_path}")
    
    # 6. Convert / Export to PDF
    compile_pdf(geometry_data, svg_path, pdf_path, theme)
    
    # 7. Convert / Export to PNG natively using pypdfium2
    png_path = f"{output_base_path}.png"
    try:
        import pypdfium2 as pdfium
        logger.info(f"Natively rendering high-resolution PNG using pypdfium2 from {pdf_path}...")
        doc = pdfium.PdfDocument(pdf_path)
        page = doc[0]
        bitmap = page.render(scale=5)  # Render page at 5x resolution (Ultra High DPI, approx 360 DPI)
        pil_img = bitmap.to_pil()
        pil_img.save(png_path, "PNG")
        logger.info(f"PNG drawing successfully compiled at: {png_path}")
    except Exception as png_err:
        logger.warning(f"Optional PNG compilation skipped: {png_err}")
        
    return svg_path, pdf_path

def draw_dimension_callout(dwg, group, dim, theme):
    """
    Renders clean, micro-animated engineering dimension lines, arrowheads,
    and text dimension markers using standard styles.
    """
    p1, p2 = dim["start"], dim["end"]
    text = dim["text"]
    offset = dim.get("offset", 15)
    
    # Dimension calculations
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle = math.atan2(dy, dx)
    
    # Orthogonal vector for offset
    ox = -math.sin(angle) * offset
    oy = math.cos(angle) * offset
    
    # Dimension line points
    dp1 = (p1[0] + ox, p1[1] + oy)
    dp2 = (p2[0] + ox, p2[1] + oy)
    
    dim_group = dwg.g(stroke=theme["dimension"], stroke_width=0.25)
    
    # 1. Extension lines from geometries
    dim_group.add(dwg.line(start=(p1[0] + ox * 0.1, p1[1] + oy * 0.1), end=(dp1[0] + ox * 0.15, dp1[1] + oy * 0.15), stroke_dasharray=[2, 2], stroke=theme["border"]))
    dim_group.add(dwg.line(start=(p2[0] + ox * 0.1, p2[1] + oy * 0.1), end=(dp2[0] + ox * 0.15, dp2[1] + oy * 0.15), stroke_dasharray=[2, 2], stroke=theme["border"]))
    
    # 2. Core dimension line
    dim_group.add(dwg.line(start=dp1, end=dp2))
    
    # 3. Arrowheads
    arrow_len = 3.5
    arrow_w = 1.0
    
    def add_arrowhead(tip, angle_offset):
        ax1 = tip[0] - arrow_len * math.cos(angle + angle_offset) - arrow_w * math.sin(angle + angle_offset)
        ay1 = tip[1] - arrow_len * math.sin(angle + angle_offset) + arrow_w * math.cos(angle + angle_offset)
        ax2 = tip[0] - arrow_len * math.cos(angle + angle_offset) + arrow_w * math.sin(angle + angle_offset)
        ay2 = tip[1] - arrow_len * math.sin(angle + angle_offset) - arrow_w * math.cos(angle + angle_offset)
        
        dim_group.add(dwg.polygon(points=[tip, (ax1, ay1), (ax2, ay2)], fill=theme["dimension"]))
        
    add_arrowhead(dp1, math.pi)  # pointing towards p1
    add_arrowhead(dp2, 0)        # pointing towards p2
    
    # 4. Text annotation
    tx = (dp1[0] + dp2[0]) / 2
    ty = (dp1[1] + dp2[1]) / 2 - 1.5  # shift slightly upwards
    
    text_rot = math.degrees(angle)
    # Normalize rotation for readable orientation
    if text_rot > 90:
        text_rot -= 180
    elif text_rot < -90:
        text_rot += 180
        
    text_elem = dwg.text(
        text, 
        insert=(tx, ty), 
        font_size=3.0, 
        fill=theme["text"], 
        text_anchor="middle", 
        font_family="Inter, Roboto, sans-serif"
    )
    if abs(text_rot) > 1.0:
        text_elem.rotate(text_rot, center=(tx, ty))
        
    group.add(dim_group)
    group.add(text_elem)

def compile_pdf(geometry_data, svg_path, pdf_path, theme):
    """
    Attempts high-fidelity SVG->PDF compilation via cairosvg.
    Falls back to building a beautiful vector PDF drawing via reportlab if dependencies are missing.
    """
    if HAS_CAIROSVG:
        try:
            logger.info("Compiling PDF from SVG using cairosvg...")
            cairosvg.svg2pdf(url=svg_path, write_to=pdf_path)
            logger.info(f"PDF compiled successfully at: {pdf_path}")
            return
        except Exception as e:
            logger.warning(f"cairosvg conversion failed: {e}. Falling back to reportlab compilation.")
            
    if HAS_REPORTLAB:
        try:
            logger.info("Generating PDF drawing replica using reportlab...")
            # Set sheet sizes
            width_mm = geometry_data.get("width", 297)
            height_mm = geometry_data.get("height", 210)
            
            # Points scale: 1mm = 2.83464 points
            pt = 2.83464
            w_pt = width_mm * pt
            h_pt = height_mm * pt
            
            c = canvas.Canvas(pdf_path, pagesize=(w_pt, h_pt))
            
            # Fill Background
            c.setFillColor(theme["bg"])
            c.rect(0, 0, w_pt, h_pt, fill=True, stroke=False)
            
            # Draw Border margins
            margin_pt = 10 * pt
            c.setStrokeColor(theme["border"])
            c.setLineWidth(0.8)
            c.rect(margin_pt, margin_pt, w_pt - 2*margin_pt, h_pt - 2*margin_pt, fill=False, stroke=True)
            
            # Replicate view geometry
            if "views" in geometry_data:
                for view_name, view in geometry_data["views"].items():
                    # Draw lines
                    for line in view.get("lines", []):
                        style = line.get("style", "visible")
                        c.setStrokeColor(theme[style])
                        c.setLineWidth(1.2 if style == "visible" else 0.6)
                        if style == "hidden":
                            c.setDash([3*pt, 2*pt])
                        elif style == "center":
                            c.setDash([6*pt, 3*pt, 1*pt, 3*pt])
                        else:
                            c.setDash([])
                            
                        p1_x, p1_y = line["start"][0] * pt, h_pt - line["start"][1] * pt
                        p2_x, p2_y = line["end"][0] * pt, h_pt - line["end"][1] * pt
                        c.line(p1_x, p1_y, p2_x, p2_y)
                        
                    # Draw circles
                    for circle in view.get("circles", []):
                        style = circle.get("style", "visible")
                        c.setStrokeColor(theme[style])
                        c.setLineWidth(1.2 if style == "visible" else 0.6)
                        if style == "center":
                            c.setDash([6*pt, 3*pt, 1*pt, 3*pt])
                        else:
                            c.setDash([])
                            
                        cx, cy = circle["center"][0] * pt, h_pt - circle["center"][1] * pt
                        cr = circle["radius"] * pt
                        c.circle(cx, cy, cr, stroke=True, fill=False)
                        
                    # Draw texts
                    c.setFillColor(theme["text"])
                    c.setFont("Helvetica-Bold", 4.0 * pt)
                    # Title
                    title_x = view["center"][0] * pt
                    title_y = h_pt - (view["center"][1] - 35) * pt
                    c.drawCentredString(title_x, title_y, view["title"])
                    
                    # Draw bolt holes (ReportLab)
                    for hole in view.get("bolt_holes", []):
                        c.setStrokeColor(theme["bolt"])
                        c.setLineWidth(0.8)
                        c.setDash([])
                        hc_x, hc_y = hole["center"][0] * pt, h_pt - hole["center"][1] * pt
                        hr = hole["radius"] * pt
                        c.circle(hc_x, hc_y, hr, stroke=True, fill=False)
                        
                        # Add crosshairs
                        c.setStrokeColor(theme["center"])
                        c.setLineWidth(0.3)
                        c.line(hc_x - hr - 2*pt, hc_y, hc_x + hr + 2*pt, hc_y)
                        c.line(hc_x, hc_y - hr - 2*pt, hc_x, hc_y + hr + 2*pt)
                        
                    # Draw dimensions (ReportLab)
                    for dim in view.get("dimensions", []):
                        p1, p2 = dim["start"], dim["end"]
                        text = dim["text"]
                        offset = dim.get("offset", 15)
                        
                        dx = p2[0] - p1[0]
                        dy = p2[1] - p1[1]
                        angle = math.atan2(dy, dx)
                        
                        ox = -math.sin(angle) * offset
                        oy = math.cos(angle) * offset
                        
                        p1_x, p1_y = p1[0] * pt, h_pt - p1[1] * pt
                        p2_x, p2_y = p2[0] * pt, h_pt - p2[1] * pt
                        
                        ox_pt = ox * pt
                        oy_pt = -oy * pt  # Y is inverted in ReportLab vs SVG
                        
                        dp1_x, dp1_y = p1_x + ox_pt, p1_y + oy_pt
                        dp2_x, dp2_y = p2_x + ox_pt, p2_y + oy_pt
                        
                        # Extension lines (dashed)
                        c.setStrokeColor(theme["border"])
                        c.setLineWidth(0.4)
                        c.setDash([2*pt, 2*pt])
                        c.line(p1_x + ox_pt * 0.1, p1_y + oy_pt * 0.1, dp1_x + ox_pt * 0.15, dp1_y + oy_pt * 0.15)
                        c.line(p2_x + ox_pt * 0.1, p2_y + oy_pt * 0.1, dp2_x + ox_pt * 0.15, dp2_y + oy_pt * 0.15)
                        
                        # Core dimension line
                        c.setStrokeColor(theme["dimension"])
                        c.setLineWidth(0.6)
                        c.setDash([])
                        c.line(dp1_x, dp1_y, dp2_x, dp2_y)
                        
                        # Arrowheads
                        arrow_len = 3.5 * pt
                        arrow_w = 1.0 * pt
                        
                        def draw_rl_arrowhead(tip_x, tip_y, is_start):
                            d_len = math.hypot(dp2_x - dp1_x, dp2_y - dp1_y)
                            if d_len > 0:
                                u_x = (dp2_x - dp1_x) / d_len
                                u_y = (dp2_y - dp1_y) / d_len
                            else:
                                u_x, u_y = 1, 0
                                
                            v_x = -u_y
                            v_y = u_x
                            
                            factor = -1 if is_start else 1
                            back_x = tip_x - factor * arrow_len * u_x
                            back_y = tip_y - factor * arrow_len * u_y
                            
                            p_left_x = back_x - arrow_w * v_x
                            p_left_y = back_y - arrow_w * v_y
                            p_right_x = back_x + arrow_w * v_x
                            p_right_y = back_y + arrow_w * v_y
                            
                            path = c.beginPath()
                            path.moveTo(tip_x, tip_y)
                            path.lineTo(p_left_x, p_left_y)
                            path.lineTo(p_right_x, p_right_y)
                            path.close()
                            c.setFillColor(theme["dimension"])
                            c.drawPath(path, fill=True, stroke=False)
                            
                        draw_rl_arrowhead(dp1_x, dp1_y, is_start=True)
                        draw_rl_arrowhead(dp2_x, dp2_y, is_start=False)
                        
                        # Text annotation
                        tx = (dp1_x + dp2_x) / 2
                        ty = (dp1_y + dp2_y) / 2
                        
                        d_len = math.hypot(dp2_x - dp1_x, dp2_y - dp1_y)
                        if d_len > 0:
                            v_x = -(dp2_y - dp1_y) / d_len
                            v_y = (dp2_x - dp1_x) / d_len
                        else:
                            v_x, v_y = 0, 1
                            
                        tx += v_x * 2.5 * pt * (1.0 if offset >= 0 else -1.0)
                        ty += v_y * 2.5 * pt * (1.0 if offset >= 0 else -1.0)
                        
                        c.setFillColor(theme["text"])
                        c.setFont("Helvetica", 3.0 * pt)
                        
                        # Rotate text to match line angle
                        text_rot = math.degrees(math.atan2(dp2_y - dp1_y, dp2_x - dp1_x))
                        if text_rot > 90:
                            text_rot -= 180
                        elif text_rot < -90:
                            text_rot += 180
                            
                        c.saveState()
                        c.translate(tx, ty)
                        c.rotate(text_rot)
                        c.drawCentredString(0, -1.0 * pt, text)
                        c.restoreState()
                    
            else:
                # Single drawing mode lines
                c.setStrokeColor(theme["visible"])
                c.setLineWidth(1.0)
                for line in geometry_data.get("lines", []):
                    # Direct scaling approximation for simple display
                    p1_x = line["start"][0] * (w_pt / geometry_data["width"])
                    p1_y = h_pt - line["start"][1] * (h_pt / geometry_data["height"])
                    p2_x = line["end"][0] * (w_pt / geometry_data["width"])
                    p2_y = h_pt - line["end"][1] * (h_pt / geometry_data["height"])
                    c.line(p1_x, p1_y, p2_x, p2_y)
                    
            # Draw title block replica (bottom right corner)
            tb_x = w_pt - margin_pt - 110*pt
            tb_y = margin_pt
            c.setFillColor(theme["title_bg"])
            c.setStrokeColor(theme["border"])
            c.rect(tb_x, tb_y, 110*pt, 30*pt, fill=True, stroke=True)
            
            c.setFillColor(theme["text"])
            c.setFont("Helvetica-Bold", 3.5 * pt)
            c.drawString(tb_x + 5*pt, tb_y + 22*pt, "DRAFTFORGE")
            c.setFont("Courier", 2.8 * pt)
            c.setFillColor(theme["title_text"])
            c.drawString(tb_x + 5*pt, tb_y + 12*pt, f"FILE: {geometry_data.get('file_name', 'UNKNOWN_SOURCE')[:20]}")
            c.drawString(tb_x + 5*pt, tb_y + 4*pt, f"DATE: {datetime.now().strftime('%Y-%m-%d')}")
            
            c.drawString(tb_x + 65*pt, tb_y + 12*pt, f"SRC: {geometry_data.get('source', 'UNKNOWN').upper()}")
            c.drawString(tb_x + 65*pt, tb_y + 4*pt, "SCALE: 1:1 [A4]")
            
            c.save()
            logger.info(f"PDF replica drawn successfully via reportlab at: {pdf_path}")
            
        except Exception as re_err:
            logger.error(f"Reportlab compilation failed: {re_err}")
    else:
        logger.warning("No PDF compilation tools available. PDF drawing skipped.")
