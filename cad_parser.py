import os
import sys
import logging
import subprocess
import json

logger = logging.getLogger("3d2d_pipeline.cad_parser")

# ---------------------------------------------------------------------------
# Discover FreeCAD — needed only to confirm it's installed
# ---------------------------------------------------------------------------
HAS_FREECAD = False
_freecad_python = None   # the FreeCAD-bundled Python executable

def _find_freecad_python():
    """
    Return the path to the Python interpreter bundled with FreeCAD,
    or fall back to the system Python that has FREECAD_LIB_PATH set.
    """
    # macOS: FreeCAD.app ships its own Python
    candidates = [
        "/Applications/FreeCAD.app/Contents/Resources/bin/python",
        "/Applications/FreeCAD.app/Contents/MacOS/python",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # Linux: usually the system python can import FreeCAD after lib is on path
    return sys.executable


def _discover_freecad():
    global HAS_FREECAD, _freecad_python
    py = _find_freecad_python()

    # Quick test: can that python import FreeCAD?
    lib_path = "/Applications/FreeCAD.app/Contents/Resources/lib"
    env = os.environ.copy()
    if os.path.isdir(lib_path):
        env["PYTHONPATH"] = lib_path + os.pathsep + env.get("PYTHONPATH", "")

    try:
        res = subprocess.run(
            [py, "-c", "import FreeCAD, Part; print('ok')"],
            capture_output=True, text=True, timeout=15, env=env
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

def project_3d_cad(file_path, output_svg_path, views=None, disc_pts=24):
    """
    Project a 3D IGES/STEP file to 2D orthographic views using OCCT.

    Parameters
    ----------
    file_path : str
        Path to the input 3D CAD file (.igs / .iges / .step / .stp).
    output_svg_path : str
        Base output path (used to derive the result JSON filename).
    views : list[str], optional
        Views to generate: 'top', 'front', 'side', 'iso'.
    disc_pts : int, optional
        Edge discretisation density (default 24 — good balance of fidelity/speed).

    Returns
    -------
    dict
        geometry_data dict with views, svg_paths, dimensions, and metadata.
    """
    if views is None:
        views = ["top", "front", "side"]

    if not HAS_FREECAD:
        raise RuntimeError(
            "FreeCAD / OpenCascade is not available on this system. "
            "Install FreeCAD from https://www.freecad.org/ and retry."
        )

    logger.info(f"OCCT projection: '{file_path}' views={views}")
    return _run_occt_subprocess(file_path, output_svg_path, views, disc_pts)


def _run_occt_subprocess(file_path, output_svg_path, views, disc_pts):
    """
    Execute occt_projector.py in an isolated subprocess (protects the
    Streamlit host process from OCCT C++ crashes on corrupt files).
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    projector_script = os.path.join(script_dir, "occt_projector.py")

    # Derive a unique temp output base from the requested output path
    out_base = os.path.splitext(os.path.abspath(output_svg_path))[0]
    result_json = out_base + "_result.json"

    # Write config JSON for the subprocess
    args_path = os.path.join(script_dir, "freecad_args.json")
    config = {
        "input_file":  os.path.abspath(file_path),
        "output_file": out_base,
        "views":       views,
        "disc_pts":    disc_pts,
    }

    # Clean stale result file
    if os.path.exists(result_json):
        try:
            os.remove(result_json)
        except OSError:
            pass

    # Build environment with OCCT lib path
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
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        if result.stdout:
            for line in result.stdout.strip().splitlines():
                logger.info(f"[occt_projector] {line}")
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                logger.warning(f"[occt_projector stderr] {line}")

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
