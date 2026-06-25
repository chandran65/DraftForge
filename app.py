import os
import shutil
import tempfile
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

selected_view = st.sidebar.selectbox(
    "CAD Projection to Generate",
    options=["top", "front", "side", "iso"],
    index=0,
    format_func=lambda v: {
        "top":   "⬆️  Top View",
        "front": "⬛  Front View",
        "side":  "◀️  Right Side View",
        "iso":   "🔷  Isometric View",
    }[v],
    help="Choose which orthographic or isometric projection to render on the sheet."
)
selected_views = [selected_view]

# Subsampling density (only applicable to CAD path)
subsample_rate = st.sidebar.slider(
    "Wireframe Detail Index",
    min_value=1,
    max_value=20,
    value=1,
    help="Performance detail slider. 1: Full extreme 3D resolution. 20: Subsampled wireframe for lightweight rendering."
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
                        status.write("🧬 Mathematically projecting 3D wireframes to orthographic views...")
                        geometry_data = project_3d_cad(input_temp_path, f"{output_base}.svg", views=selected_views)
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

                    st.markdown("#### Download Blueprint Formats")
                    st.caption("Select your target high-precision export formats below:")

                    col1, col2 = st.columns(2)

                    # 1. Download SVG button
                    if os.path.exists(svg_out):
                        with open(svg_out, "rb") as file:
                            col1.download_button(
                                label="⬇️ Download SVG (Vector)",
                                data=file,
                                file_name=f"{os.path.splitext(file_name)[0]}.svg",
                                mime="image/svg+xml",
                                use_container_width=True,
                            )

                    # 2. Download PDF button
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
