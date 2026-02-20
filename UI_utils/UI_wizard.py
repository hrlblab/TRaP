from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QMessageBox
)
from UI_utils.UI_Config_Manager import ConfigManagerUI, ConfigManager
from UI_utils.UI_Spectrum_Response_Correction_Factor import SpectrumCorrectionProcessUI
from UI_utils.UI_Calibration import WaveformSelectionUI
from UI_utils.UI_P_Mean_Process import P_Mean_Process_UI
from UI_utils.UI_P_Mean_Batch_Process import BatchPMeanUI

class SystemSelectWizard(QWidget):
    """A step-by-step wizard for the Raman processing workflow."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Raman Process Wizard")
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(400, int(screen.width() * 0.9)), min(500, int(screen.height() * 0.9)))
        self.move(screen.center() - self.rect().center())

        # Workflow step labels
        self.steps = [
            "Config Manager",
            "Spectrum Response Correction",
            "WL Calibration",
            "Spectrum Response Correction (Again)",
            "X-Axis Calibration",
            "Spectrum Process",
            "Spectrum Batch Process"
        ]
        self.step = 0
        self.opened_windows = []         # Keep track of open child windows
        self.config = ConfigManager()

        self._build_ui()
        self._update_buttons()

    def _build_ui(self):
        """Set up the logo, all step buttons, and the Reset button."""
        layout = QVBoxLayout(self)

        # Logo (optional)
        logo = QLabel(self)
        pix = QPixmap('vanderbilt_biophotonics_center_logo.jpg')
        logo.setPixmap(pix.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        # Create a button for each step
        self.buttons = []
        for title in self.steps:
            btn = QPushButton(title, self)
            btn.clicked.connect(self._on_step)
            layout.addWidget(btn)
            self.buttons.append(btn)

        # Add a Reset button to restart from SRF
        self.btn_reset = QPushButton("Reset to SRF", self)
        self.btn_reset.clicked.connect(self._reset_to_srf)
        layout.addWidget(self.btn_reset)

    def _update_buttons(self):
        """Enable/disable buttons based on current step, and highlight the active one."""
        for i, btn in enumerate(self.buttons):
            # Step 0 (Config Manager) is always enabled
            if i == 0:
                btn.setEnabled(True)
                btn.setStyleSheet("font-weight:bold;" if self.step == 0 else "")
                continue

            # After step 5, enable both Spectrum Process (5) and Batch Process (6)
            if self.step >= 5 and i in (5, 6):
                btn.setEnabled(True)
                btn.setStyleSheet("font-weight:bold;")
            elif i == self.step:
                # Only the current step button is enabled and bold
                btn.setEnabled(True)
                btn.setStyleSheet("font-weight:bold;")
            else:
                btn.setEnabled(False)
                btn.setStyleSheet("")

    def _on_step(self):
        """Handle clicks on step buttons."""
        idx = self.buttons.index(self.sender())
        # Guard: only handle the active step (or steps 5/6 when self.step >=5)
        if idx != self.step and not (self.step >= 5 and idx in (5, 6)):
            return

        # Step 0: Configuration Manager
        if idx == 0:
            win = ConfigManagerUI()
            win.config_updated.connect(self._after_config)
            win.show()
            self.opened_windows.append(win)

        # Step 1: Spectrum Response Correction (SRF)
        elif idx == 1:
            dlg = SpectrumCorrectionProcessUI(self)
            if dlg.exec_():
                # If user needs X-Axis calibration → go to WL Calibration
                if dlg.result == "RequireXAxisCalibration":
                    self.step = 2
                else:
                    # Factor exists → skip WL and second SRF → go to X-Axis
                    self.step = 4
                self._update_buttons()

        # Step 2: White-Light (WL) Calibration
        elif idx == 2:
            wl_win = WaveformSelectionUI()
            wl_win.show()
            self.opened_windows.append(wl_win)
            QMessageBox.information(
                self,
                "WL Calibration",
                "Please complete WL calibration in the new window, then close it."
            )
            # After WL, go back to SRF (again)
            self.step = 3
            self._update_buttons()

        # Step 3: Spectrum Response Correction (Again)
        elif idx == 3:
            dlg2 = SpectrumCorrectionProcessUI(self)
            if dlg2.exec_():
                # If still require X-Axis → loop back to WL Calibration
                if dlg2.result == "RequireXAxisCalibration":
                    self.step = 2
                else:
                    # Otherwise proceed to X-Axis Calibration
                    self.step = 4
                self._update_buttons()

        # Step 4: X-Axis Calibration
        elif idx == 4:
            x_win = WaveformSelectionUI()  # or your dedicated X-Axis UI
            x_win.show()
            self.opened_windows.append(x_win)
            QMessageBox.information(
                self,
                "X-Axis Calibration",
                "Please complete X-Axis calibration in the new window, then close it."
            )
            self.step = 5
            self._update_buttons()

        # Step 5: Spectrum Data Process
        elif idx == 5:
            sp_win = P_Mean_Process_UI()
            sp_win.show()
            self.opened_windows.append(sp_win)
            # Stay at step >= 5 so batch is also enabled

        # Step 6: Spectrum Batch Process
        elif idx == 6:
            batch_win = BatchPMeanUI()
            batch_win.show()
            self.opened_windows.append(batch_win)
            # Stay at step >= 5

    def _after_config(self):
        """Callback when Config Manager saves settings."""
        self.step = 1  # Move to Spectrum Response Correction
        self._update_buttons()
        QMessageBox.information(
            self, "Next Step",
            "Configuration saved successfully. Proceed to Spectrum Response Correction."
        )

    def _reset_to_srf(self):
        """Reset the flow to the Spectrum Response Correction step."""
        self.step = 1
        self._update_buttons()
        QMessageBox.information(
            self, "Reset",
            "Workflow has been reset. Please start from Spectrum Response Correction."
        )

    def closeEvent(self, event):
        """Ensure all child windows are closed when wizard exits."""
        for win in self.opened_windows:
            win.close()
        event.accept()