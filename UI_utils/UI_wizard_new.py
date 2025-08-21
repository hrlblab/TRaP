from PyQt5.QtCore import Qt, QEasingCurve, QPropertyAnimation, QRect
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox, QFrame, QScrollArea, QGraphicsDropShadowEffect, QSizePolicy
)

# ---------------------------
# Modern look & feel helpers
# ---------------------------

def apply_modern_style(app):
    """Apply a global dark modern stylesheet."""
    app.setStyleSheet("""
        QWidget {
            font-family: 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif;
            color: #EAEAEA;
            background: #121212;
        }
        QLabel#Title { font-size: 36px; font-weight: 600; }
        QLabel#Subtitle { color:#8B8B8B; }
        QPushButton {
            border: none;
            padding: 10px 14px;
            border-radius: 10px;
            background: #1F1F1F;
        }
        QPushButton:hover { background: #2A2A2A; }
        QPushButton:pressed { background: #343434; }
        QPushButton[cta="true"] {
            background: #4C8BF5; color: white;
        }
        QPushButton[cta="true"]:hover { background: #5B97F7; }
        QPushButton[cta="true"]:pressed { background: #3B78E5; }

        /* Left rail step buttons */
        QPushButton.step {
            text-align: left;
            padding: 10px 12px;
            border-radius: 8px;
            background: transparent;
        }
        QPushButton.step:hover { background: rgba(255,255,255,0.06); }
        QPushButton.step[active="true"] {
            background: rgba(76,139,245,0.18);
            color: #BFD6FF;
            font-weight: 600;
        }

        QFrame#card { background: #171717; border-radius: 14px; }
        QScrollArea { background: transparent; border: none; }
    """)


class ModernCard(QFrame):
    """Rounded card with shadow."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(Qt.black)
        self.setGraphicsEffect(shadow)


class ModernShell(QWidget):
    """
    Shell layout: left step rail + right content card.
    It can drive the inner wizard by calling its hidden buttons.
    """
    def __init__(self, content_widget: QWidget, step_titles, on_step_request):
        """
        :param content_widget: your SystemSelectWizard instance
        :param step_titles: list of step titles
        :param on_step_request: callable(idx) to ask wizard to trigger a step
        """
        super().__init__()
        self.content_widget = content_widget
        self.step_titles = step_titles
        self.on_step_request = on_step_request
        self.step_buttons = []
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # Left rail (steps)
        left = QVBoxLayout()
        left.setSpacing(10)

        # App logo & titles
        logo = QLabel()
        pix = QPixmap('vanderbilt_biophotonics_center_logo.jpg')
        logo.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        left.addWidget(logo)

        title = QLabel("Raman Processing")
        title.setObjectName("Title")
        left.addWidget(title)

        subtitle = QLabel("Step-by-step workflow")
        subtitle.setObjectName("Subtitle")
        left.addWidget(subtitle)
        left.addSpacing(8)

        # Build step buttons in the rail
        for i, t in enumerate(self.step_titles):
            b = QPushButton(f"{i}. {t}")
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("class", "step")  # For readability; style uses 'step' class
            b.setProperty("active", False)
            b.setMinimumHeight(36)
            b.setObjectName("stepBtn")
            b.setAccessibleName("step")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setStyleSheet("")  # style from global sheet (QPushButton.step)
            b.setProperty("role", "step")
            b.setProperty("step", True)
            # Add icon if you have qrc icons (optional):
            # b.setIcon(QIcon(":/icons/xxx.svg"))
            b.clicked.connect(lambda _, idx=i: self._on_nav_clicked(idx))
            b.setProperty("cssClass", "step")  # not used by Qt default, just a tag
            b.setStyleSheet("QPushButton { }")  # ensure refresh
            b.setProperty("class", "step")
            self.step_buttons.append(b)
            left.addWidget(b)

        left.addStretch(1)

        # Right card contains the content widget
        right_card = ModernCard()
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.content_widget)
        right_layout.addWidget(scroll)

        root.addLayout(left, 1)
        root.addWidget(right_card, 3)

    def _on_nav_clicked(self, idx: int):
        """Ask the wizard to run the step logic; shell doesn't decide rules."""
        if callable(self.on_step_request):
            self.on_step_request(idx)

    def set_active_step(self, idx: int):
        """Highlight the active step in the left rail."""
        for i, b in enumerate(self.step_buttons):
            b.setProperty("active", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)


def animate_step_change(widget: QWidget):
    """Simple slide-in animation for the content area."""
    start_rect = QRect(widget.x() + 20, widget.y(), widget.width(), widget.height())
    end_rect = QRect(widget.x(), widget.y(), widget.width(), widget.height())
    anim = QPropertyAnimation(widget, b"geometry", widget)
    anim.setDuration(220)
    anim.setStartValue(start_rect)
    anim.setEndValue(end_rect)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()


# ---------------------------
# Your original wizard (minimal changes)
# ---------------------------

from UI_utils.UI_Config_Manager import ConfigManagerUI, ConfigManager
from UI_utils.UI_Spectrum_Response_Correction_Factor import SpectrumCorrectionProcessUI
from UI_utils.UI_Calibration import WaveformSelectionUI
from UI_utils.UI_P_Mean_Process import P_Mean_Process_UI
from UI_utils.UI_P_Mean_Batch_Process import BatchPMeanUI


class SystemSelectWizard(QWidget):
    """A step-by-step wizard for the Raman processing workflow (reordered)."""
    def __init__(self, shell_bridge=None):
        """
        :param shell_bridge: optional callable idx->None.
                             If provided, wizard will notify shell to sync active step.
        """
        super().__init__()
        self.setWindowTitle("Raman Process Wizard")
        # Wider aspect works better inside shell
        self.setMinimumSize(720, 520)

        # New ordered workflow:
        # 0: Config Manager
        # 1: Calibration (only if not already present)
        # 2: White-Light Correction
        # 3: P-Mean Process
        # 4: Batch Process
        self.steps = [
            "Config Manager",
            "X-axis Calibration",
            "Spectra Response Correction",
            "Spectrum Process",
            "Spectrum Batch Process"
        ]
        self.step = 0
        self.opened_windows = []      # Keep track of opened child windows
        self.config = ConfigManager()  # Your existing config manager
        self._shell_sync = shell_bridge  # to sync left-rail highlight

        # Hidden internal buttons used to keep your existing _on_step logic.
        # We DO NOT add them into the visible layout; shell will "click" them by index.
        self.buttons = [QPushButton(t, self) for t in self.steps]
        for i, b in enumerate(self.buttons):
            b.clicked.connect(self._on_step)
            b.hide()  # keep them invisible; they are just triggers

        self._build_ui()
        self._update_buttons(first_time=True)

    # ---------------------------
    # UI helpers
    # ---------------------------
    def _build_ui(self):
        """Build a simple title + CTA area; content is mostly external dialogs."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        header = QLabel("Workflow")
        header.setObjectName("Title")
        header_desc = QLabel("Use the left rail to navigate. Primary actions appear here.")
        header_desc.setObjectName("Subtitle")

        # Primary CTA for current step (optional)
        self.btn_primary = QPushButton("Run Current Step")
        self.btn_primary.setProperty("cta", True)
        self.btn_primary.clicked.connect(lambda: self._request_step(self.step))

        # Put inside a card for a modern look
        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)
        card_layout.addWidget(header)
        card_layout.addWidget(header_desc)
        card_layout.addWidget(self.btn_primary)
        card_layout.addStretch(1)

        layout.addWidget(card)

    def _update_buttons(self, first_time=False):
        """Enable/disable internal triggers based on current step."""
        for i, btn in enumerate(self.buttons):
            if i == 0:
                btn.setEnabled(True)
                continue
            # After step >= 3, enable both Spectrum Process (3) and Batch Process (4)
            if self.step >= 3 and i in (3, 4):
                btn.setEnabled(True)
            elif i == self.step:
                btn.setEnabled(True)
            else:
                btn.setEnabled(False)

        # Sync left rail highlight via shell, if available
        if callable(self._shell_sync):
            self._shell_sync(self.step)

        # Small slide-in animation for the content area (only after first build)
        if not first_time:
            animate_step_change(self)

    # Public method for shell: ask wizard to trigger step idx
    def request_step_from_shell(self, idx: int):
        """Called by shell when user clicks a left-rail step."""
        self._request_step(idx)

    def _request_step(self, idx: int):
        """Centralized guard + trigger."""
        # Guard: only handle the active step (or steps 3/4 when self.step >=3)
        if idx != self.step and not (self.step >= 3 and idx in (3, 4)):
            return
        # Trigger your original logic by 'clicking' the hidden button
        self.buttons[idx].click()

    # ---------------------------
    # Flow control (same logic as before)
    # ---------------------------
    def _on_step(self):
        """Handle clicks on (hidden) step buttons."""
        idx = self.buttons.index(self.sender())

        # Step 0: Config Manager
        if idx == 0:
            win = ConfigManagerUI()
            win.config_updated.connect(self._after_config_saved)
            win.show()
            self.opened_windows.append(win)

        # Step 1: Calibration (only when calibration is missing)
        elif idx == 1:
            if self._has_calibration():
                QMessageBox.information(
                    self, "Calibration",
                    "Calibration already found in configuration. Skipping to White Light Correction."
                )
                self.step = 2
                self._update_buttons()
                return

            cal_win = WaveformSelectionUI()
            cal_win.show()
            self.opened_windows.append(cal_win)
            QMessageBox.information(
                self, "Calibration",
                "Please complete Calibration in the new window, then close it."
            )
            self.step = 2
            self._update_buttons()

        # Step 2: White-Light Correction
        elif idx == 2:
            dlg = SpectrumCorrectionProcessUI(self)
            if hasattr(dlg, "exec_"):
                if dlg.exec_():
                    # If still require X-Axis Calibration → go back to Calibration
                    if getattr(dlg, "result", None) == "RequireXAxisCalibration":
                        self.step = 1  # back to Calibration
                    else:
                        self.step = 3  # into P-Mean Process
                    self._update_buttons()
            else:
                dlg.show()
                self.opened_windows.append(dlg)
                QMessageBox.information(
                    self, "White Light Correction",
                    "Please complete White Light Correction in the new window, then close it."
                )
                self.step = 3
                self._update_buttons()

        # Step 3: Spectrum Data Process (P-Mean)
        elif idx == 3:
            sp_win = P_Mean_Process_UI()
            sp_win.show()
            self.opened_windows.append(sp_win)
            # Stay at step >= 3 to keep Batch enabled

        # Step 4: Spectrum Batch Process
        elif idx == 4:
            batch_win = BatchPMeanUI()
            batch_win.show()
            self.opened_windows.append(batch_win)
            # Stay at step >= 3

    def _after_config_saved(self):
        """Callback when Config Manager saves settings."""
        if self._has_calibration():
            self.step = 2
            next_msg = "Configuration saved. Calibration found. Proceed to White Light Correction."
        else:
            self.step = 1
            next_msg = "Configuration saved. No Calibration found. Please complete Calibration first."
        self._update_buttons()
        QMessageBox.information(self, "Next Step", next_msg)

    def closeEvent(self, event):
        """Ensure all child windows are closed when wizard exits."""
        for win in self.opened_windows:
            try:
                win.close()
            except Exception:
                pass
        event.accept()

    # ---------------------------
    # Utilities
    # ---------------------------
    def _has_calibration(self) -> bool:
        """Heuristic check for whether calibration exists in configuration."""
        try:
            possible_keys = [
                "CalibrationFile", "WvnFile", "wvn_file",
                "x_axis_calibration_file", "x_calib_file", "XCalibCoeffs", "Wvn"
            ]
            # Dict-like
            if hasattr(self.config, "get"):
                for k in possible_keys:
                    val = self.config.get(k)
                    if self._is_present(val):
                        return True
            # Attributes
            for k in possible_keys:
                val = getattr(self.config, k, None)
                if self._is_present(val):
                    return True
            # Nested dicts
            for container_attr in ["config", "state", "settings"]:
                container = getattr(self.config, container_attr, None)
                if isinstance(container, dict):
                    for k in possible_keys:
                        if k in container and self._is_present(container[k]):
                            return True
            return False
        except Exception:
            return False

    @staticmethod
    def _is_present(val) -> bool:
        """Generic presence check for str/list/dict/ndarray-like."""
        if isinstance(val, str) and val.strip():
            return True
        if isinstance(val, (list, tuple, dict)) and len(val) > 0:
            return True
        try:
            import numpy as np
            if isinstance(val, np.ndarray) and val.size > 0:
                return True
        except Exception:
            pass
        return False


# ---------------------------
# How to run (example main)
# ---------------------------

# if __name__ == "__main__":
#     import sys
#     app = QApplication(sys.argv)
#     apply_modern_style(app)
#
#     # Build the wizard
#     # We create the shell AFTER the wizard so shell can call wizard.request_step_from_shell.
#     # We also pass a bridge to sync highlight.
#     wizard = SystemSelectWizard()
#
#     # Build shell: left rail + right content
#     # Define 'on_step_request' to forward the index to wizard.
#     shell = ModernShell(
#         content_widget=wizard,
#         step_titles=wizard.steps,
#         on_step_request=wizard.request_step_from_shell
#     )
#
#     # Give the wizard a callback to sync left-rail highlight:
#     wizard._shell_sync = shell.set_active_step
#
#     shell.resize(1024, 680)
#     shell.setWindowTitle("Raman Process")
#     shell.show()
#     sys.exit(app.exec_())
