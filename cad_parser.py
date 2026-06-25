import os
import sys
import logging
import subprocess
import json

logger = logging.getLogger("3d2d_pipeline.cad_parser")

# ---------------------------------------------------------------------------
# Discover FreeCAD bundled Python
# ---------------------------------------------------------------------------
HAS_FREECAD = False
_freecad_python = None


def _find_freecad_python():
    candidates = [
        "/Applications/FreeCAD.app/Contents/Resources/bin/python",
        "/Applications/FreeCAD.app/Contents/MacOS/python",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return sys.executable


def _discover_freecad():
    global HAS_FREECAD, _freecad_python
    py = _find_freecad_python()
    lib_path = "/Applications/FreeCAD.app/Contents/Resources/lib"
    env = os.environ.copy()
    if os.path.isdir(lib_path):
        env["PYTHONPATH"] = lib_path + os.pathsep + env.get("PYTHONPATH", "")
    try:
        res = subprocess.run(
            [py, "-c", "import FreeCAD, Part; print('ok')"],
            capture_output=True, text=True, timeout=15, env=env,
        )
        if res.returncode == 0 and "ok" in res.stdout:
            HAS_FREECAD = True
            _freecad_python = py
            logger.info(f"FreeCAD available via: {py}")
            return True
    except Exception as e:
        logger.debug(f"FreeCAD discovery failed: {e}")
    logger.warning("FreeCAD / OpenCascade not found on this system.")
    return False


_discover_freecad()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def project_3d_cad(file_path, output_svg_path, views=None, render_mode="2d_wireframe", disc_pts=24):
    """
    Project a 3D IGES/STEP file to 2D using OCCT.

    Parameters
    ----------
    file_path : str
        Path to the input 3D CAD file (.igs / .iges / .step / .stp).
    output_svg_path : str
        Base output path (used to derive the result JSON filename).
    views : list[str], optional
        Single-element list with the view name:
        'initial', 'bottom', 'front', 'back', 'left', 'right'
    render_mode : str, optional
        One of: '2d_wireframe', '3d_wireframe', '3d_hidden_lines',
                '3d_flat_shading', '3d_smooth_shading'
    disc_pts : int, optional
        Edge discretisation density (default 24).

    Returns
    -------
    dict
        geometry_data compatible with DraftForge renderer.
    """
    if views is None:
        views = ["front"]

    if not HAS_FREECAD:
        raise RuntimeError(
            "FreeCAD / OpenCascade is not available on this system. "
            "Install FreeCAD from https://www.freecad.org/ and retry."
        )

    view_name = views[0] if views else "front"
    logger.info(f"OCCT projection: '{file_path}' view={view_name} mode={render_mode}")
    return _run_occt_subprocess(file_path, output_svg_path, view_name, render_mode, disc_pts)


def _run_occt_subprocess(file_path, output_svg_path, view_name, render_mode, disc_pts):
    """Execute occt_projector.py in an isolated subprocess."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    projector_script = os.path.join(script_dir, "occt_projector.py")

    out_base = os.path.splitext(os.path.abspath(output_svg_path))[0]
    result_json = out_base + "_result.json"

    args_path = os.path.join(script_dir, "freecad_args.json")
    config = {
        "input_file":  os.path.abspath(file_path),
        "output_file": out_base,
        "view_name":   view_name,
        "render_mode": render_mode,
        "disc_pts":    disc_pts,
    }

    if os.path.exists(result_json):
        try:
            os.remove(result_json)
        except OSError:
            pass

    env = os.environ.copy()
    lib_path = "/Applications/FreeCAD.app/Contents/Resources/lib"
    if os.path.isdir(lib_path):
        env["PYTHONPATH"] = lib_path + os.pathsep + env.get("PYTHONPATH", "")

    try:
        with open(args_path, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Spawning OCCT subprocess: {_freecad_python} {projector_script}")
        result = subprocess.run(
            [_freecad_python, projector_script],
            capture_output=True, text=True, timeout=180, env=env,
        )

        if result.stdout:
            for line in result.stdout.strip().splitlines():
                logger.info(f"[occt] {line}")
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                logger.warning(f"[occt stderr] {line}")

        if result.returncode != 0 or not os.path.exists(result_json):
            raise RuntimeError(
                f"OCCT subprocess failed (exit {result.returncode}).\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

        with open(result_json, "r") as f_res:
            geometry_data = json.load(f_res)

        logger.info("OCCT projection completed successfully.")
        return geometry_data

    finally:
        for tmp in [args_path, result_json]:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
