# -*- coding: utf-8 -*-
# TRaP_GUI.py - Main entry point for TRaP Application
# All comments in English.

import sys
import ctypes
import platform
from PyQt5.QtCore import QSharedMemory, QCoreApplication, Qt
from PyQt5.QtWidgets import QApplication, QMessageBox

# Import from the new optimized wizard v2
from UI_utils.UI_wizard_v2 import (
    SystemSelectWizard,
    ModernShell,
    apply_modern_style
)

APP_ID = 'TRaP.1.0'


def main():
    # High-DPI friendly flags (must be set BEFORE QApplication)
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Windows taskbar fix: AppUserModelID
    if platform.system() == 'Windows':
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    # Create QApplication FIRST so QMessageBox is safe to use
    app = QApplication(sys.argv)

    # Apply modern dark theme
    apply_modern_style(app)

    # Single instance guard with QSharedMemory
    shared_mem = QSharedMemory(APP_ID)
    if not shared_mem.create(512):
        QMessageBox.warning(None, "Warning", "Application is already running!")
        sys.exit(1)

    # Build wizard
    wizard = SystemSelectWizard()

    # Wrap wizard with ModernShell for app-like layout with left navigation rail
    shell = ModernShell(
        content_widget=wizard,
        step_titles=SystemSelectWizard.STEPS,  # Use class constant STEPS
        on_step_request=wizard.request_step_from_shell
    )

    # Connect wizard to shell for step synchronization
    wizard._shell_sync = shell.set_active_step
    wizard._shell = shell  # For step skipping functionality

    shell.setWindowTitle("TRaP - Raman Processing Application")
    screen = app.primaryScreen().availableGeometry()
    shell.resize(min(1024, int(screen.width() * 0.9)), min(680, int(screen.height() * 0.9)))
    shell.move(screen.center() - shell.rect().center())
    shell.show()

    # Execute application loop
    exit_code = app.exec_()

    # Detach shared memory on exit
    try:
        shared_mem.detach()
    except Exception:
        pass

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
