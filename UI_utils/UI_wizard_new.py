from PyQt5.QtCore import Qt, QEasingCurve, QPropertyAnimation, QRect
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox, QFrame, QScrollArea, QGraphicsDropShadowEffect, QSizePolicy,
    QCheckBox
)

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
    """Left rail + right content card."""
    def __init__(self, content_widget: QWidget, step_titles, on_step_request):
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

        # left rail
        left = QVBoxLayout()
        left.setSpacing(10)

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

        for i, t in enumerate(self.step_titles):
            b = QPushButton(f"{i}. {t}")
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("class", "step")
            b.setProperty("active", False)
            b.setMinimumHeight(36)
            b.setObjectName("stepBtn")
            b.setAccessibleName("step")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.clicked.connect(lambda _, idx=i: self._on_nav_clicked(idx))
            self.step_buttons.append(b)
            left.addWidget(b)

        left.addStretch(1)

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
        if callable(self.on_step_request):
            self.on_step_request(idx)

    def set_active_step(self, idx: int):
        for i, b in enumerate(self.step_buttons):
            b.setProperty("active", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)


def animate_step_change(widget: QWidget):
    start_rect = QRect(widget.x() + 20, widget.y(), widget.width(), widget.height())
    end_rect = QRect(widget.x(), widget.y(), widget.width(), widget.height())
    anim = QPropertyAnimation(widget, b"geometry", widget)
    anim.setDuration(220)
    anim.setStartValue(start_rect)
    anim.setEndValue(end_rect)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()


# ---------------------------
# Wizard with step-0-only toggles & responsive description
# ---------------------------

from UI_utils.UI_Config_Manager import ConfigManagerUI, ConfigManager
# from UI_utils.UI_Spectrum_Response_Correction_Factor import SpectrumCorrectionProcessUI  # Old UI
from UI_utils.UI_SRCF import SRCF_UI  # New Spectral Response Correction Factor UI
from UI_utils.UI_Calibration import WaveformSelectionUI
from UI_utils.UI_P_Mean_Process import P_Mean_Process_UI
from UI_utils.UI_P_Mean_Batch_Process import BatchPMeanUI


class SystemSelectWizard(QWidget):
    """A step-by-step wizard (reordered) with step-0-only toggles."""
    def __init__(self, shell_bridge=None):
        super().__init__()
        self.setWindowTitle("Raman Process Wizard")
        self.setMinimumSize(720, 520)

        self.steps = [
            "Config Manager",
            "X-axis Calibration",
            "Spectra Response Correction",
            "Spectrum Process",
            "Spectrum Batch Process"
        ]
        self.step = 0
        self.opened_windows = []
        self.config = ConfigManager()
        self._shell_sync = shell_bridge

        self.has_calibration_file = False
        self.has_response_correction = False

        self.step_desc = {
            0: "Edit and save your instrument/system parameters here. After saving or loading a config, this window closes automatically. "
               "If you already have the X-axis calibration (.mat) and/or spectral response correction file, enable the toggles below to skip Step 1/2.",
            1: "Calibrate the X-axis (wavenumber). If you already have a .mat calibration file, go back to Step 0 and enable the toggle to skip.",
            2: "Apply or confirm spectral response correction. If already prepared, go back to Step 0 and enable the toggle to skip.",
            3: "Process a single spectrum step-by-step (baseline, response correction, truncate, binning, polyfit/FBS, noise smoothing, normalization).",
            4: "Run P-Mean batch processing on multiple spectra with the same configuration."
        }

        # 隐藏触发按钮
        self.buttons = [QPushButton(t, self) for t in self.steps]
        for b in self.buttons:
            b.clicked.connect(self._on_step)
            b.hide()

        self._build_ui()
        self._update_step_header()
        self._update_buttons(first_time=True)
        self._update_visibility_per_step()

    # ---------- UI ----------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        header = QLabel("Workflow")
        header.setObjectName("Title")


        self.header_desc = QLabel("")
        self.header_desc.setObjectName("Subtitle")
        self.header_desc.setWordWrap(True)

        self.header_desc.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.header_desc.setMinimumWidth(10)

        top_bar = QHBoxLayout()
        self.chk_has_cal = QCheckBox("I already have Calibration")
        self.chk_has_cal.stateChanged.connect(self._toggle_has_cal)
        self.chk_has_resp = QCheckBox("I already have Response Correction")
        self.chk_has_resp.stateChanged.connect(self._toggle_has_resp)

        self.btn_back_to_zero = QPushButton("Back to Step 0")
        self.btn_back_to_zero.clicked.connect(lambda: self._jump_to_step0())

        top_bar.addWidget(self.chk_has_cal)
        top_bar.addWidget(self.chk_has_resp)
        top_bar.addStretch(1)
        top_bar.addWidget(self.btn_back_to_zero)

        self.btn_primary = QPushButton("Run " + self.steps[self.step])
        self.btn_primary.setProperty("cta", True)
        self.btn_primary.clicked.connect(lambda: self._request_step(self.step))

        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)
        card_layout.addWidget(header)
        card_layout.addWidget(self.header_desc)
        card_layout.addLayout(top_bar)
        card_layout.addWidget(self.btn_primary)
        card_layout.addStretch(1)

        layout.addWidget(card)

    def _update_visibility_per_step(self):
        show_toggles = (self.step == 0)
        self.chk_has_cal.setVisible(show_toggles)
        self.chk_has_resp.setVisible(show_toggles)

    def _update_step_header(self):
        self.header_desc.setText(self.step_desc.get(self.step, ""))

    def _toggle_has_cal(self, _state):
        self.has_calibration_file = self.chk_has_cal.isChecked()

    def _toggle_has_resp(self, _state):
        self.has_response_correction = self.chk_has_resp.isChecked()

    def _jump_to_step0(self):
        self.step = 0
        self._update_buttons()
        self._update_step_header()
        self._update_visibility_per_step()

    # ---------- Buttons/state ----------
    def _update_buttons(self, first_time=False):
        for i, btn in enumerate(self.buttons):
            if i == 0:
                btn.setEnabled(True)
                continue
            if self.step >= 3 and i in (3, 4):
                btn.setEnabled(True)
            elif i == self.step:
                btn.setEnabled(True)
            else:
                btn.setEnabled(False)

        if callable(self._shell_sync):
            self._shell_sync(self.step)
        if not first_time:
            animate_step_change(self)

    def request_step_from_shell(self, idx: int):
        self._request_step(idx)

    def _request_step(self, idx: int):
        if idx != self.step and not (self.step >= 3 and idx in (3, 4)):
            return
        self.buttons[idx].click()

    # ---------- Flow ----------
    def _on_step(self):
        idx = self.buttons.index(self.sender())

        # Step 0: Config Manager
        if idx == 0:
            win = ConfigManagerUI()
            win.config_updated.connect(self._after_config_saved)
            win.show()
            self.opened_windows.append(win)

        # Step 1: Calibration
        elif idx == 1:
            if self.has_calibration_file:
                QMessageBox.information(self, "Calibration",
                                        "Calibration file already provided. Skipping to Step 2.")
                self.step = 2
                self._update_buttons()
                self._update_step_header()
                self._update_visibility_per_step()
                return

            cal_win = WaveformSelectionUI()
            cal_win.show()
            self.opened_windows.append(cal_win)
            QMessageBox.information(self, "Calibration",
                                    "Complete the calibration in the opened window, then close it.")
            self.step = 2
            self._update_buttons()
            self._update_step_header()
            self._update_visibility_per_step()

        # Step 2: Response Correction
        elif idx == 2:
            if self.has_response_correction:
                QMessageBox.information(self, "Response Correction",
                                        "Response correction already provided. Skipping to Spectrum Process.")
                self.step = 3
                self._update_buttons()
                self._update_step_header()
                self._update_visibility_per_step()
                return

            # Old UI (commented out):
            # dlg = SpectrumCorrectionProcessUI(self)
            # if hasattr(dlg, "exec_"):
            #     if dlg.exec_():
            #         if getattr(dlg, "result", None) == "RequireXAxisCalibration" and not self.has_calibration_file:
            #             self.step = 1
            #         else:
            #             self.step = 3
            #         self._update_buttons()
            #         self._update_step_header()
            #         self._update_visibility_per_step()
            # else:
            #     dlg.show()
            #     self.opened_windows.append(dlg)
            #     QMessageBox.information(self, "White Light Correction",
            #                             "Complete the correction in the new window, then close it.")
            #     self.step = 3
            #     self._update_buttons()
            #     self._update_step_header()
            #     self._update_visibility_per_step()

            # New UI (SRCF_UI):
            dlg = SRCF_UI(self)
            if dlg.exec_():
                if getattr(dlg, "result", None) == "RequireXAxisCalibration" and not self.has_calibration_file:
                    self.step = 1
                else:
                    self.step = 3
                self._update_buttons()
                self._update_step_header()
                self._update_visibility_per_step()
            else:
                # User cancelled
                pass

        # Step 3: Spectrum Process
        elif idx == 3:
            sp_win = P_Mean_Process_UI()
            sp_win.show()
            self.opened_windows.append(sp_win)

        # Step 4: Batch
        elif idx == 4:
            batch_win = BatchPMeanUI()
            batch_win.show()
            self.opened_windows.append(batch_win)

    def _after_config_saved(self):
        """
        Config：
         - has_calibration_file → Skip Step 1
         - has_response_correction → Skip Step 2
        """
        if self.has_calibration_file and self.has_response_correction:
            self.step = 3
            msg = "Config updated. Calibration/Response ready. Go to Spectrum Process."
        elif self.has_calibration_file and not self.has_response_correction:
            self.step = 2
            msg = "Config updated. Calibration ready. Next: Response Correction."
        else:
            self.step = 1
            msg = "Config updated. Start with X-axis Calibration."
        self._update_buttons()
        self._update_step_header()
        self._update_visibility_per_step()
        QMessageBox.information(self, "Next Step", msg)

    def closeEvent(self, event):
        for win in getattr(self, "opened_windows", []):
            try:
                win.close()
            except Exception:
                pass
        event.accept()
