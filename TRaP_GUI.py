# -*- coding: utf-8 -*-
# All comments in English as requested.

import sys
import ctypes
import platform
from PyQt5.QtCore import QSharedMemory, QCoreApplication, Qt
from PyQt5.QtWidgets import QApplication, QMessageBox

# Your wizard (and possibly shell & style helper) live here:
# Ensure UI_wizard_new.py exposes SystemSelectWizard, ModernShell, apply_modern_style
from UI_utils.UI_wizard_new import SystemSelectWizard

# Optional imports: if you defined these in the same module as wizard
try:
    from UI_utils.UI_wizard_new import ModernShell, apply_modern_style
    HAS_SHELL = True
except Exception:
    ModernShell = None
    apply_modern_style = None
    HAS_SHELL = False

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

    # Create QApplication FIRST so QMessageBox is safe to use.
    app = QApplication(sys.argv)

    # Apply modern dark theme if available
    if apply_modern_style is not None:
        apply_modern_style(app)

    # Single instance guard with QSharedMemory
    shared_mem = QSharedMemory(APP_ID)
    if not shared_mem.create(512):
        # Safe now because QApplication exists
        QMessageBox.warning(None, "Warning", "Application is already running!")
        sys.exit(1)

    # Build wizard
    wizard = SystemSelectWizard()

    # If ModernShell exists, wrap the wizard for the app-like layout
    if HAS_SHELL and ModernShell is not None:
        # Wire shell <-> wizard bridge so left-rail highlights stay in sync
        shell = ModernShell(
            content_widget=wizard,
            step_titles=wizard.steps,
            on_step_request=wizard.request_step_from_shell  # shell clicks -> wizard
        )
        # wizard notifies shell which step is active
        if hasattr(wizard, "_shell_sync"):
            wizard._shell_sync = shell.set_active_step

        shell.setWindowTitle("Raman Process")
        shell.resize(1024, 680)
        shell.show()
    else:
        # Fallback: show the wizard directly (no shell)
        wizard.resize(900, 600)
        wizard.show()

    # Exec app loop
    exit_code = app.exec_()

    # Detach shared memory on exit
    try:
        shared_mem.detach()
    except Exception:
        pass

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
