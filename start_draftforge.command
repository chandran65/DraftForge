#!/bin/bash
# Move to the script's directory
cd "$(dirname "$0")"

echo "=================================================="
echo "          🔥 Starting DraftForge Engine 🔥        "
echo "=================================================="

# Check if FreeCAD is installed
if [ ! -d "/Applications/FreeCAD.app" ]; then
    echo "FreeCAD.app not found in /Applications. Installing FreeCAD v1.1.1..."
    chmod +x install_freecad.sh
    ./install_freecad.sh
else
    echo "FreeCAD is already installed."
fi

echo "Verifying Python dependencies..."
/Applications/FreeCAD.app/Contents/Resources/bin/python -m pip install -r requirements.txt

echo "Launching DraftForge Streamlit Web App..."
PYTHONPATH=/Applications/FreeCAD.app/Contents/Resources/lib /Applications/FreeCAD.app/Contents/Resources/bin/python -m streamlit run app.py
