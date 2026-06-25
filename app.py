import os
import shutil
import tempfile
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Add local path import context and custom setup override final
import importlib
import cad_parser
import pdf_parser
import renderer

# Force reload helper modules to bypass Streamlit's in-memory import cache
importlib.reload(cad_parser)
importlib.reload(pdf_parser)
importlib.reload(renderer)

from cad_parser import project_3d_cad
from pdf_parser import parse_drawing
from renderer import render_pipeline_output, THEMES

# Set page configuration with a premium engineering title and icon
st.set_page_config(
    page_title="DraftForge — 3D→2D CAD Drafting Engine",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium CSS — minimal overrides; native Streamlit theme handles all widget colors
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
    /* Typography */
    .title-header, .subtitle-header, .glass-panel, label, button {
        font-family: 'Outfit', sans-serif !important;
    }
    div[data-testid="stMetricValue"], code, pre, .subtitle-header {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* Page Title */
    .title-header {
        color: #0F172A !important;
        font-weight: 800;
        font-size: 2.2rem;
        text-align: center;
        margin-top: 10px;
        margin-bottom: 2px;
        letter-spacing: -0.5px;
    }
    .subtitle-header {
        color: #0284C7 !important;
        text-align: center;
        font-size: 0.8rem;
        letter-spacing: 4px;
        margin-bottom: 25px;
        text-transform: uppercase;
        font-weight: 600;
    }
    
    /* Custom HTML card panels */
    .glass-panel {
        background: #ffffff !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 12px !important;
        padding: 20px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
        margin-bottom: 20px !important;
    }
    .glass-panel:hover {
        border-color: #0284C7 !important;
        box-shadow: 0 2px 8px rgba(2,132,199,0.08) !important;
    }
    
    /* Metric cards polish */
    div[data-testid="stMetricValue"] {
        color: #0284C7 !important;
        font-weight: 700 !important;
    }
    
    /* Primary button gradient */
    div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, #0284C7 0%, #06B6D4 100%) !important;
        color: #ffffff !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# 1. Page Header Elements
st.markdown("<h1 class='title-header'>🔥 DraftForge</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle-header'>3D→2D AUTOMATED CAD DRAFTING ENGINE</p>", unsafe_allow_html=True)

# 2. Sidebar Configuration Panel
st.sidebar.markdown("### ⚙️ Pipeline Settings")
uploaded_file = st.sidebar.file_uploader(
    "Upload 3D solid model (.igs/.step) or 2D drawing",
    type=["igs", "iges", "step", "stp", "pdf", "png", "jpg", "jpeg"],
    help="Accepts native 3D IGES/STEP CAD models or 2D technical drawings."
)

# Configurable options
selected_theme = st.sidebar.selectbox(
    "Drawing Aesthetic Sheet",
    options=["light", "dark"],
    index=0,
    help="Light: standard white paper blueprint. Dark: modern high-tech obsidian blueprint."
)

_VIEW_LABELS = {
    "initial": "🏠  Initial (Top)",
    "bottom":  "⬇️  Bottom",
    "left":    "◀️  Left",
    "right":   "▶️  Right",
    "front":   "⬛  Front",
    "back":    "🔁  Back",
}
selected_view = st.sidebar.selectbox(
    "View Direction",
    options=list(_VIEW_LABELS.keys()),
    index=0,
    format_func=lambda v: _VIEW_LABELS[v],
    help="Choose the orthographic projection direction.",
)
selected_views = [selected_view]

_MODE_LABELS = {
    "2d_wireframe":    "✏️  2D Wireframe",
    "3d_wireframe":    "🔲  3D Wireframe",
    "3d_hidden_lines": "〰️  3D Hidden Lines",
    "3d_flat_shading": "🔷  3D Flat Shading",
    "3d_smooth_shading":"🌅  3D Smooth Shading",
}
selected_render_mode = st.sidebar.selectbox(
    "Render Mode",
    options=list(_MODE_LABELS.keys()),
    index=0,
    format_func=lambda m: _MODE_LABELS[m],
    help="2D Wireframe: flat edges. 3D Wireframe: depth-based edge weights. Hidden Lines: dashed back edges. Flat/Smooth Shading: filled faces with lighting.",
)


# Sidebar footer
st.sidebar.markdown("---")
st.sidebar.caption("🔥 **DraftForge v2.0**")
st.sidebar.caption("3D→2D Automated Drafting Engine")

# 3. Main Application Orchestration
if uploaded_file is not None:
    file_name = uploaded_file.name
    file_ext = os.path.splitext(file_name.lower())[1]
    
    # Track file changes to reset conversion state
    if "active_file" not in st.session_state or st.session_state.active_file != file_name:
        st.session_state.active_file = file_name
        st.session_state.converted = False
        
    if not st.session_state.converted:
        # Show upload success and ready state
        st.markdown(f"""
        <div class='glass-panel' style='border-left: 5px solid #0284C7;'>
            <h3 style='color: #0F172A; margin-top: 0; font-family: Outfit, sans-serif; font-weight: 600; letter-spacing: -0.5px;'>📂 CAD Model Loaded Successfully</h3>
            <p style='color: #475569; font-size: 14px; font-family: "JetBrains Mono", monospace; margin-bottom: 0;'>
                <span style='color: #0284C7; font-weight: bold;'>File:</span> {file_name}<br>
                <span style='color: #0284C7; font-weight: bold;'>Status:</span> <span style='color: #16A34A; font-weight: bold;'>● READY FOR PROJECTION</span>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style='margin-bottom: 20px; font-family: Outfit, sans-serif; font-size: 14px; color: #0284C7; background: rgba(2, 132, 199, 0.05); border: 1px solid rgba(2, 132, 199, 0.15); padding: 12px 18px; border-radius: 8px;'>
            👈 Adjust your sheet style and views in the sidebar, then click the button below to project the model.
        </div>
        """, unsafe_allow_html=True)
        
        # Big glowing conversion button
        if st.button("🔥 Forge Blueprint", type="primary", use_container_width=True):
            st.session_state.converted = True
            st.rerun()
            
    else:
        # We allow them to reset/re-run if they change their parameters
        if st.button("🔄 Reset / Re-project Model", use_container_width=True):
            st.session_state.converted = False
            st.rerun()
            
        with tempfile.TemporaryDirectory() as temp_dir:
            input_temp_path = os.path.join(temp_dir, file_name)
            with open(input_temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            output_base = os.path.join(temp_dir, "draft_output")
            
            # Run conversion terminal with detailed step-by-step progress logging
            with st.status("🔥 DraftForge — Forging Blueprint...", expanded=True) as status:
                try:
                    # Step 1: Discover & project geometries
                    status.write("📂 Loading CAD model and discovering boundary entities...")
                    cad_exts = {".igs", ".iges", ".step", ".stp"}
                    if file_ext in cad_exts:
                        mode_label = _MODE_LABELS.get(selected_render_mode, selected_render_mode)
                        status.write(f"🧬 Projecting **{_VIEW_LABELS.get(selected_view, selected_view)}** — {mode_label}...")
                        geometry_data = project_3d_cad(
                            input_temp_path,
                            f"{output_base}.svg",
                            views=selected_views,
                            render_mode=selected_render_mode,
                        )
                    else:
                        status.write("🔍 Extracting 2D vectors and OpenCV blueprint paths...")
                        geometry_data = parse_drawing(input_temp_path)
                        
                    if not geometry_data:
                        st.error("Failed to extract geometry data from the uploaded file.")
                        st.stop()
                        
                    # Step 2: Render & Compile
                    status.write("📐 Compiling vector drafting canvas with borders & annotations...")
                    svg_out, pdf_out = render_pipeline_output(geometry_data, output_base, theme_name=selected_theme)
                    
                    # Step 3: Read SVG for inline preview
                    status.write("🖼️ Preparing vector drawing preview...")
                            
                    # Update status to complete
                    status.update(label="🔥 DraftForge — Blueprint Forged!", state="complete", expanded=False)
                    
                    st.success("DraftForge — Blueprint Forged Successfully!")
                    
                    # Dynamic diagnostics transparency expander
                    with st.expander("🔍 Pipeline Diagnostics & Model Topology", expanded=True):
                        st.markdown("### ⚙️ Conversion Engine Analytics")
                        
                        # Compute statistics
                        total_lines = 0
                        total_circles = 0
                        total_holes = 0
                        total_dims = 0
                        total_svg_paths = 0
                        
                        if "views" in geometry_data:
                            for view_name, view_data in geometry_data["views"].items():
                                total_lines += len(view_data.get("lines", []))
                                total_circles += len(view_data.get("circles", []))
                                total_holes += len(view_data.get("bolt_holes", []))
                                total_dims += len(view_data.get("dimensions", []))
                                total_svg_paths += len(view_data.get("svg_paths", []))
                        
                        # Columns for Engine Mode and Topology stats
                        col_engine, col_topology = st.columns(2)
                        
                        with col_engine:
                            st.markdown("**Core Conversion Engine Mode**")
                            source = geometry_data.get("source", "unknown")
                            if "occt" in source:
                                st.success("🟢 OCCT Edge Projection Engine (FreeCAD/OpenCascade)")
                            elif source == "cad_freecad":
                                st.success("🟢 Headless 3D FreeCAD Engine")
                            elif source == "cad_iges_native":
                                st.info("⚡ Pure-Python 3D IGES Projector")
                            else:
                                st.warning("🌌 Procedural B-Rep Synthesizer")
                                
                            # Show file info
                            st.write(f"**Input File Name:** `{file_name}`")
                            
                            # Show procedural hash metadata if available
                            meta = geometry_data.get("meta", {})
                            if meta:
                                thash = meta.get("hash_val", "N/A")
                                st.write(f"**Filename Hash Signature:** `{thash}`")
                                
                        with col_topology:
                            st.markdown("**Projected 2D Geometry Vector Count**")
                            if total_svg_paths:
                                st.write(f"🧬 **OCCT Projected Edges:** `{total_svg_paths}`")
                            st.write(f"📈 **Projected Lines:** `{total_lines}`")
                            st.write(f"⭕ **Concentric Circles:** `{total_circles}`")
                            st.write(f"🔴 **Bolt Hole Crosshairs:** `{total_holes}`")
                            st.write(f"📐 **Linear & Diameter Dimensions:** `{total_dims}`")
                            
                        # Show custom mathematical parameters for procedural parts
                        meta = geometry_data.get("meta", {})
                        if meta and "params" in meta:
                            st.markdown("---")
                            st.markdown("🧬 **Deterministic Part Dimensions** (Synthesized from filename signature)")
                            
                            # Render them nicely as a grid
                            param_cols = st.columns(3)
                            for i, (param_name, param_val) in enumerate(meta["params"].items()):
                                col_idx = i % 3
                                param_cols[col_idx].metric(label=param_name, value=param_val)
                    
                    st.markdown("### 📥 Export Portal")

                    # ── Inline SVG preview (full fidelity, no cropping) ──────────
                    if os.path.exists(svg_out):
                        with open(svg_out, "r", encoding="utf-8") as f_svg:
                            svg_content = f_svg.read()
                        # Embed SVG inside a scrollable, bordered container
                        components.html(
                            f"""
                            <div style="
                                background:#f8fafc;
                                border:1px solid #CBD5E1;
                                border-radius:10px;
                                padding:16px;
                                overflow:auto;
                                margin-bottom:16px;
                            ">
                                <div style="display:flex;justify-content:center;">
                                    {svg_content}
                                </div>
                            </div>
                            """,
                            height=600,
                            scrolling=True,
                        )

                    # ── Store in session_state for hole editor ────────────────
                    st.session_state["_gd"]       = geometry_data
                    st.session_state["_svg_out"]  = svg_out
                    st.session_state["_pdf_out"]  = pdf_out
                    st.session_state["_out_base"] = output_base
                    st.session_state["_theme"]    = selected_theme
                    st.session_state["_fname"]    = file_name

                    st.markdown("#### Download Blueprint Formats")
                    st.caption("Select your target high-precision export formats below:")

                    col1, col2 = st.columns(2)
                    if os.path.exists(svg_out):
                        with open(svg_out, "rb") as file:
                            col1.download_button(
                                label="⬇️ Download SVG (Vector)",
                                data=file,
                                file_name=f"{os.path.splitext(file_name)[0]}.svg",
                                mime="image/svg+xml",
                                use_container_width=True,
                            )
                    if os.path.exists(pdf_out):
                        with open(pdf_out, "rb") as file:
                            col2.download_button(
                                label="⬇️ Download PDF (Vector Document)",
                                data=file,
                                file_name=f"{os.path.splitext(file_name)[0]}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                            )

                except Exception as e:
                    st.exception(e)
                    st.error(f"Pipeline encountered a compilation error: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# Hole Dimensions & Editor  (persists across reruns via session_state)
# ═══════════════════════════════════════════════════════════════════════════
if "_gd" in st.session_state:
    gd          = st.session_state["_gd"]
    _out_base   = st.session_state["_out_base"]
    _theme      = st.session_state["_theme"]
    _fname      = st.session_state["_fname"]

    # Collect all holes from all views
    all_holes = []
    for vname, vdata in gd.get("views", {}).items():
        for h in vdata.get("holes", []):
            all_holes.append({
                "ID":          h.get("id", "?"),
                "View":        vname,
                "Diameter (mm)": float(h.get("diameter", 0)),
                "Depth (mm)":   float(h.get("depth", 0)),
                "X mm":        round(h["center_3d"][0], 3) if h.get("center_3d") else 0,
                "Y mm":        round(h["center_3d"][1], 3) if h.get("center_3d") else 0,
                "Z mm":        round(h["center_3d"][2], 3) if h.get("center_3d") else 0,
                "_view":       vname,   # hidden key for mapping back
                "_idx":        h.get("id", "?"),
            })

    with st.expander(f"🔩 Detected Holes & Dimensions  ({len(all_holes)} found)", expanded=bool(all_holes)):
        if not all_holes:
            st.info("No circular holes detected in this view/model. Try the **Initial (Top)** view which shows holes as circles.")
        else:
            st.markdown(
                "**Edit** Diameter or Depth values below, then click **Apply Changes** "
                "to update the annotations on the drawing."
            )
            st.caption("ℹ️ Editing values here changes the *callout labels* on the drawing — the underlying CAD geometry is unchanged.")

            df = pd.DataFrame(all_holes)
            display_cols = ["ID", "View", "Diameter (mm)", "Depth (mm)", "X mm", "Y mm", "Z mm"]
            edited_df = st.data_editor(
                df[display_cols],
                num_rows="fixed",
                use_container_width=True,
                column_config={
                    "ID":             st.column_config.TextColumn("ID", disabled=True, width="small"),
                    "View":           st.column_config.TextColumn("View", disabled=True, width="small"),
                    "Diameter (mm)":  st.column_config.NumberColumn("⌀ Diameter (mm)", min_value=0.0, step=0.01, format="%.3f"),
                    "Depth (mm)":     st.column_config.NumberColumn("↧ Depth (mm)", min_value=0.0, step=0.01, format="%.3f"),
                    "X mm":           st.column_config.NumberColumn("X (mm)", disabled=True, format="%.3f"),
                    "Y mm":           st.column_config.NumberColumn("Y (mm)", disabled=True, format="%.3f"),
                    "Z mm":           st.column_config.NumberColumn("Z (mm)", disabled=True, format="%.3f"),
                },
                key="hole_editor",
            )

            col_apply, col_info = st.columns([1, 3])
            apply_clicked = col_apply.button("🔄 Apply Changes & Re-render", type="primary", use_container_width=True)
            col_info.caption("Updates ⌀ callout labels on drawing with your edited values, then re-generates SVG/PDF.")

            if apply_clicked:
                # Map edited values back into geometry_data holes
                id_to_row = {row["ID"]: row for row in edited_df.to_dict(orient="records")}
                for vname, vdata in gd.get("views", {}).items():
                    for h in vdata.get("holes", []):
                        hid = h.get("id", "?")
                        if hid in id_to_row:
                            row = id_to_row[hid]
                            new_d = row["Diameter (mm)"]
                            new_dep = row["Depth (mm)"]
                            h["diameter"]  = new_d
                            h["depth"]     = new_dep
                            dep_str = f" ↧{new_dep:.2f}" if new_dep > 0.05 else ""
                            h["label"] = f"⌀{new_d:.2f}{dep_str}"

                # Re-render with updated labels
                with st.spinner("Re-rendering drawing with updated hole annotations..."):
                    from renderer import render_pipeline_output
                    new_svg, new_pdf = render_pipeline_output(gd, _out_base + "_edited", theme_name=_theme)

                st.success("Drawing updated!")

                # Show updated SVG inline
                if os.path.exists(new_svg):
                    with open(new_svg, "r", encoding="utf-8") as f_s:
                        new_svg_content = f_s.read()
                    components.html(
                        f"""
                        <div style="background:#f8fafc;border:2px solid #0284C7;border-radius:10px;
                                    padding:16px;overflow:auto;margin-bottom:12px;">
                            <div style="display:flex;justify-content:center;">
                                {new_svg_content}
                            </div>
                        </div>
                        """,
                        height=600, scrolling=True,
                    )
                    col_dl1, col_dl2 = st.columns(2)
                    with open(new_svg, "rb") as f_dl:
                        col_dl1.download_button(
                            "⬇️ Download Updated SVG",
                            data=f_dl,
                            file_name=f"{os.path.splitext(_fname)[0]}_edited.svg",
                            mime="image/svg+xml",
                            use_container_width=True,
                        )
                    if os.path.exists(new_pdf):
                        with open(new_pdf, "rb") as f_dl2:
                            col_dl2.download_button(
                                "⬇️ Download Updated PDF",
                                data=f_dl2,
                                file_name=f"{os.path.splitext(_fname)[0]}_edited.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                            )



else:
    # Welcome page when no file is uploaded yet
    st.markdown("""
    <div class='glass-panel' style='border-left: 5px solid #0284C7;'>
        <h3 style='color: #0F172A; margin-top: 0; font-family: Outfit, sans-serif; font-weight: 600; letter-spacing: -0.5px;'>👈 Welcome to DraftForge</h3>
        <p style='color: #475569; font-size: 15px; margin-bottom: 0;'>Please upload a 3D solid model (<strong>.igs / .step / .iges / .stp</strong>) or a 2D technical drawing (<strong>.pdf / .png / .jpg</strong>) in the sidebar to begin.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class='glass-panel'>
        <h3 style='color: #0284C7; margin-top: 0; font-family: Outfit, sans-serif; font-weight: 600;'>⚙️ DraftForge Pipeline Highlights</h3>
        <ul style='color: #334155; font-size: 14px; line-height: 1.6; padding-left: 20px; margin-bottom: 0;'>
            <li><strong style='color: #0F172A;'>Path A (3D CAD STEP/IGS)</strong>: Natively parses ASCII Boundary Representation solids, harvesting 3D coordinate vertices, and projects Top, Front, and Side orthographic views in pure Python.</li>
            <li><strong style='color: #0F172A;'>Path B (2D Drawings PDF/Images)</strong>: Harvests native PDF vectors using <code>pdfplumber</code> or scanned blueprints using Canny thresholds and OpenCV Hough Line segment tracing.</li>
            <li><strong style='color: #0F172A;'>Unified Canvas & Renderer</strong>: Formats curves with standard hidden dashed lines, axis centerlines, title block tags, and download exports.</li>
        </ul>
        <hr style='border: 0; border-top: 1px solid rgba(0, 0, 0, 0.08); margin: 20px 0;'>
        <p style='color: #64748B; font-size: 13px; font-family: "JetBrains Mono", monospace; margin-bottom: 0;'>
            💡 To test the pipeline out-of-the-box, you can find the sample IGES model `Input/ex3.iges` inside the <code>Input/</code> directory.
        </p>
    </div>
    """, unsafe_allow_html=True)
