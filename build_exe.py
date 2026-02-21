# -*- coding: utf-8 -*-
"""
TRaP Application Build Script
Usage: python build_exe.py [pyinstaller|nuitka]
Default: pyinstaller
"""

import subprocess
import sys
import os
import shutil

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

def check_tool_installed(tool_name):
    """Check if a tool is installed"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "show", tool_name],
                      capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def install_tool(tool_name):
    """Install a tool via pip"""
    print(f"Installing {tool_name}...")
    subprocess.run([sys.executable, "-m", "pip", "install", tool_name], check=True)

def build_with_pyinstaller():
    """Build using PyInstaller (--onedir mode for fast startup)"""
    print("=" * 50)
    print("Building with PyInstaller (--onedir mode)")
    print("=" * 50)

    if not check_tool_installed("pyinstaller"):
        install_tool("pyinstaller")

    # Clean previous builds
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",                          # Use onedir for fast startup
        "--windowed",                        # No console window
        "--name", "TRaP",                    # Output name
        "--icon", "vanderbilt_biophotonics_center_logo.jpg",  # App icon
        # Include data files
        "--add-data", "config.json;.",
        "--add-data", "configs;configs",
        "--add-data", "resources;resources",
        "--add-data", "data;data",
        "--add-data", "vanderbilt_biophotonics_center_logo.jpg;.",
        # Hidden imports
        "--hidden-import", "PyQt5.sip",
        "--hidden-import", "PyQt5.QtCore",
        "--hidden-import", "PyQt5.QtGui",
        "--hidden-import", "PyQt5.QtWidgets",
        "--hidden-import", "openpyxl",
        "--hidden-import", "openpyxl.cell",
        "--hidden-import", "openpyxl.cell._writer",
        "--hidden-import", "scipy.io",
        "--hidden-import", "scipy.io.matlab",
        "--hidden-import", "scipy.sparse",
        "--hidden-import", "scipy.linalg",
        "--hidden-import", "scipy.signal",
        "--hidden-import", "scipy.special",
        "--hidden-import", "scipy.optimize",
        "--hidden-import", "numpy.polynomial",
        "--hidden-import", "numpy.polynomial.polynomial",
        "--hidden-import", "matplotlib.backends.backend_qt5agg",
        # Collect all submodules
        "--collect-submodules", "UI_utils",
        "--collect-submodules", "utils",
        # Exclude unnecessary modules to reduce size
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib.tests",
        "--exclude-module", "numpy.tests",
        "--exclude-module", "PySide6",
        "--exclude-module", "PySide2",
        # Main script
        "TRaP_GUI.py"
    ]

    print("Running command:")
    print(" ".join(cmd))
    print()

    subprocess.run(cmd, check=True)

    print()
    print("=" * 50)
    print("Build complete!")
    print(f"Output: {os.path.join(SCRIPT_DIR, 'dist', 'TRaP', 'TRaP.exe')}")
    print("=" * 50)

def build_with_nuitka():
    """Build using Nuitka (compiles to C, fastest startup)"""
    print("=" * 50)
    print("Building with Nuitka (fastest startup)")
    print("=" * 50)

    if not check_tool_installed("nuitka"):
        install_tool("nuitka")

    # Clean previous builds
    for folder in ["TRaP_GUI.build", "TRaP_GUI.dist", "TRaP_GUI.onefile-build"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",                      # Create standalone distribution
        "--windows-console-mode=disable",    # No console window (GUI app)
        "--enable-plugin=pyqt5",             # PyQt5 plugin
        "--include-package=UI_utils",        # Include UI_utils package
        "--include-package=utils",           # Include utils package
        # Include data files
        "--include-data-files=config.json=config.json",
        "--include-data-dir=configs=configs",
        "--include-data-dir=resources=resources",
        "--include-data-dir=data=data",
        "--include-data-files=vanderbilt_biophotonics_center_logo.jpg=vanderbilt_biophotonics_center_logo.jpg",
        # Output settings
        "--output-dir=dist",
        "--output-filename=TRaP.exe",
        # Optimization
        "--assume-yes-for-downloads",        # Auto download dependencies
        # Main script
        "TRaP_GUI.py"
    ]

    print("Running command:")
    print(" ".join(cmd))
    print()

    subprocess.run(cmd, check=True)

    print()
    print("=" * 50)
    print("Build complete!")
    print(f"Output: {os.path.join(SCRIPT_DIR, 'dist', 'TRaP_GUI.dist')}")
    print("=" * 50)

def main():
    # Parse command line argument
    if len(sys.argv) > 1:
        method = sys.argv[1].lower()
    else:
        method = "pyinstaller"

    print(f"TRaP Build Script")
    print(f"Working directory: {SCRIPT_DIR}")
    print(f"Build method: {method}")
    print()

    if method == "pyinstaller":
        build_with_pyinstaller()
    elif method == "nuitka":
        build_with_nuitka()
    else:
        print(f"Unknown method: {method}")
        print("Usage: python build_exe.py [pyinstaller|nuitka]")
        sys.exit(1)

if __name__ == "__main__":
    main()
