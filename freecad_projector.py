import os
import sys
import time

# Redirect output for logging in GUI mode
sys.stdout = open('freecad_projector_run.log', 'w', buffering=1)
sys.stderr = sys.stdout

# Parse arguments from freecad_args.json
import json
args_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'freecad_args.json')
if not os.path.exists(args_path):
    print("Error: freecad_args.json not found at:", args_path)
    sys.exit(1)

with open(args_path, 'r') as f:
    config = json.load(f)

input_file = config.get('input_file')
output_file = config.get('output_file')
views = config.get('views', ['top', 'front', 'side'])

if not input_file or not output_file:
    print("Error: Missing input_file or output_file in freecad_args.json.")
    sys.exit(1)

print("=== DraftForge FreeCAD Subprocess Projector ===")
print("Input:", input_file)
print("Output:", output_file)
print("Views:", views)

import FreeCAD
import FreeCADGui
import Import
import TechDraw
import TechDrawGui

doc = FreeCAD.newDocument("ProjectionDoc")
print("Loading 3D CAD model...")
try:
    Import.insert(input_file, doc.Name)
except Exception as e:
    print("Import.insert failed:", e)

imported_objects = doc.Objects
if not imported_objects:
    print("No objects found in doc via Import.insert. Falling back to Part.read...")
    try:
        shape = Part.read(input_file)
        if shape is not None and not shape.isNull():
            obj = doc.addObject("Part::Feature", "ImportedShape")
            obj.Shape = shape
            imported_objects = [obj]
    except Exception as e:
        print("Part.read failed:", e)

if not imported_objects:
    print("Error: No imported solid found.")
    sys.exit(1)

main_solid = imported_objects[0]
print(f"Target solid: {main_solid.Name}")

# Create DrawPage
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
    print(f"Template path: {template_path}")
    template.Template = template_path
    page.Template = template
else:
    print("Warning: Template path not found.")

# Add orthographic views
direction_map = {
    'top': (0, 0, 1),
    'front': (0, -1, 0),
    'side': (1, 0, 0),
    'iso': (1, -1, 1)
}

for view_name in views:
    if view_name not in direction_map:
        continue
    print(f"Adding view: {view_name}")
    view = doc.addObject("TechDraw::DrawViewPart", f"View_{view_name}")
    view.Source = imported_objects
    view.Direction = direction_map[view_name]
    
    # Position views on A4 canvas
    if view_name == 'front':
        view.X = 80
        view.Y = 140
    elif view_name == 'top':
        view.X = 80
        view.Y = 60
    elif view_name == 'side':
        view.X = 180
        view.Y = 140
    elif view_name == 'iso':
        view.X = 180
        view.Y = 60
        
    page.addView(view)

# Show page in GUI to initialize QGraphicsScene rendering
page.ViewObject.show()

# Recompute document and allow HLR computation to complete
doc.recompute()
print("Waiting for Hidden Line Removal (HLR) solver...")
time.sleep(3.0)
doc.recompute()

# Ensure output directory exists
os.makedirs(os.path.dirname(output_file), exist_ok=True)

# Export page as SVG
print("Exporting page as SVG...")
TechDrawGui.exportPageAsSvg(page, output_file)
print("SVG Export completed.")

# Export page as PDF
output_pdf = os.path.splitext(output_file)[0] + ".pdf"
print("Exporting page as PDF...")
TechDrawGui.exportPageAsPdf(page, output_pdf)
print("PDF Export completed.")

# Clean up and exit GUI window
FreeCAD.closeDocument("ProjectionDoc")
FreeCADGui.getMainWindow().close()
print("=== Projector completed successfully ===")
sys.exit(0)
