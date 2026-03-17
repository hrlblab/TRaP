"""
PyInstaller runtime hook — runs before any imports.
Adds _MEIPASS (_internal/) to the Windows DLL search path so Qt DLLs
are found by QtCore.pyd / other extension modules.
Required for PyInstaller >= 6.x on Windows + conda PyQt5.
"""
import os
import sys

if sys.platform == "win32" and hasattr(sys, "_MEIPASS"):
    os.add_dll_directory(sys._MEIPASS)
    # Also add PyQt5/Qt5/bin if present (conda layout)
    qt5_bin = os.path.join(sys._MEIPASS, "PyQt5", "Qt5", "bin")
    if os.path.isdir(qt5_bin):
        os.add_dll_directory(qt5_bin)
