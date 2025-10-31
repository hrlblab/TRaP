# UI_SpectrumCorrectionProcess.py
# -*- coding: utf-8 -*-

"""
Qt dialog for spectral response correction workflow.

Flow:
  - Start by choosing a method: White-Light or NIST (or load existing factor)
  - White-Light: MUST load Calibration (.mat with Cal['Wvn']) + Measured WL + True WL (2-col)
  - NIST: ONLY requires polynomial coefficients + SRM measured spectrum (no Calibration required)

Relies on utils.WLCorrection for algorithms and file IO.
Exposes:
    dlg.result: str ("UseExistingFactor" | "CorrComputed" | "WvnUploaded" | "RequireXAxisCalibration" | "Cancelled")
    dlg.wvn:    np.ndarray or None
    dlg.corr:   np.ndarray or None
"""

import sys
import os
import numpy as np
from scipy.io import loadmat
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QMessageBox, QFileDialog, QFrame, QLayout
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Import core functions from your utils module
from utils.WLCorrection import (
    read_vector_file, read_2col_file, read_coeffs_file,
    wl_correction_from_true_and_measured, nist_correction_from_srm
)


class SpectrumCorrectionProcessUI(QDialog):
    """Dialog for spectral correction process (UI only)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spectrum Correction Process")
        self.setFixedSize(720, 520)

        # Data and state
        self.result = None
        self.wvn = None
        self.corr = None
        self.mode = None  # "WL", "NIST", "EXIST"

        # Files
        self.file_wl_measured = None
        self.file_srm_measured = None
        self.file_wlmax = None
        self.file_coeffs = None
        self.file_wvn_mat = None

        # Build UI
        self._build_ui()
        self._choose_method()

    # ---------------- Layout management ----------------
    def _build_ui(self):
        self.layout = QVBoxLayout(self)

        self.label_title = QLabel("", self)
        self.layout.addWidget(self.label_title)

        self.q_area = QFrame(self)
        self.q_layout = QVBoxLayout(self.q_area)
        self.layout.addWidget(self.q_area)

        self.actions = QHBoxLayout()
        self.layout.addLayout(self.actions)

        # Matplotlib figure
        self.fig = Figure(figsize=(6, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        self.layout.addWidget(self.canvas)

        # Bottom buttons
        bottom = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(btn_cancel)

        self.btn_ok = QPushButton("OK / Finish")
        self.btn_ok.clicked.connect(self._on_finish)
        self.btn_ok.setEnabled(False)
        bottom.addWidget(self.btn_ok)
        self.layout.addLayout(bottom)

    def _clear_layout(self, layout: QLayout):
        """Recursively remove all widgets and sub-layouts."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            child_layout = item.layout()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def _clear_q_area(self):
        self._clear_layout(self.q_layout)
        self._clear_layout(self.actions)

    # ---------------- Entry page ----------------
    def _choose_method(self):
        """Landing page: choose Existing / White-Light / NIST."""
        self._clear_q_area()
        self.label_title.setText("Select a correction method:")
        row = QHBoxLayout()

        btn_exist = QPushButton("Load Existing Factor")
        btn_exist.clicked.connect(self._on_have_factor)

        btn_wl = QPushButton("White-Light")
        btn_wl.clicked.connect(self._precheck_then_wl)

        btn_nist = QPushButton("NIST Standard")
        btn_nist.clicked.connect(self._ui_nist_inputs)

        row.addWidget(btn_exist)
        row.addWidget(btn_wl)
        row.addWidget(btn_nist)
        self.q_layout.addLayout(row)

    # ---------------- Common utilities ----------------
    def _load_wvn_mat(self):
        """Load Cal['Wvn'] from .mat file."""
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select X Axis Calibration File",
            "", "MAT files (*.mat);;All Files (*)"
        )
        if not fp:
            return False
        try:
            mat = loadmat(fp)
            if "Cal" in mat and isinstance(mat["Cal"], np.ndarray):
                cal_struct = mat["Cal"]
                if "Wvn" in cal_struct.dtype.names:
                    self.wvn = cal_struct["Wvn"][0, 0].flatten().astype(float)
                    self.file_wvn_mat = fp
                    self.result = "WvnUploaded"
                    QMessageBox.information(self, "Loaded", f"Wvn loaded ({len(self.wvn)} points).")
                    return True
            QMessageBox.warning(self, "Invalid File", "Missing Cal['Wvn'] in .mat file.")
            return False
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return False

    def _ensure_wvn(self) -> bool:
        """For WL: ensure Calibration is loaded."""
        if self.wvn is not None:
            return True
        reply = QMessageBox.question(
            self, "Calibration Required",
            "White-Light correction requires Calibration (.mat with Cal['Wvn']). Do you have it?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            return self._load_wvn_mat()
        else:
            QMessageBox.information(self, "Missing Calibration",
                                    "Please complete X-axis Calibration first and save as .mat.")
            self.result = "RequireXAxisCalibration"
            self._choose_method()
            return False

    # ---------------- Existing factor ----------------
    def _on_have_factor(self):
        """Load an existing correction factor."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Existing Spectral Response Factor",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not file_path:
            return
        try:
            corr = read_vector_file(file_path)
            self.corr = corr.reshape(-1)
            self.mode = "EXIST"
            self.result = "UseExistingFactor"
            self.btn_ok.setEnabled(True)
            self._clear_q_area()
            self.label_title.setText("Loaded Existing Factor")
            self._preview_curve(self.corr, "Loaded Correction Factor")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load: {e}")

    # ---------------- White-Light ----------------
    def _precheck_then_wl(self):
        if not self._ensure_wvn():
            return
        self._ui_wl_inputs()

    def _ui_wl_inputs(self):
        self.mode = "WL"
        self._clear_q_area()
        self.label_title.setText("White-Light Correction Inputs")

        btn_meas = QPushButton("Load Measured WL Spectrum (vector)")
        btn_meas.clicked.connect(self._pick_wl_measured)

        btn_ref = QPushButton("Load True WL Reference (2 columns: wavelength, intensity)")
        btn_ref.clicked.connect(self._pick_wlmax)

        btn_compute = QPushButton("Compute WL Correction")
        btn_compute.clicked.connect(self._compute_wl_corr)

        self.q_layout.addWidget(btn_meas)
        self.q_layout.addWidget(btn_ref)
        self.actions.addWidget(btn_compute)

        # Back
        btn_back = QPushButton("Back")
        btn_back.clicked.connect(self._choose_method)
        self.actions.addWidget(btn_back)

    def _pick_wl_measured(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select Measured White-Light Spectrum",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return
        try:
            _ = read_vector_file(fp)
            self.file_wl_measured = fp
            QMessageBox.information(self, "Loaded", "Measured WL selected.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read: {e}")

    def _pick_wlmax(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select True WL Reference",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return
        try:
            _ = read_2col_file(fp)
            self.file_wlmax = fp
            QMessageBox.information(self, "Loaded", "True WL reference loaded.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read: {e}")

    def _compute_wl_corr(self):
        if self.wvn is None:
            QMessageBox.warning(self, "Missing", "Calibration required.")
            return
        if not self.file_wl_measured or not self.file_wlmax:
            QMessageBox.warning(self, "Missing", "Load Measured WL and True WL first.")
            return
        try:
            wl_meas = read_vector_file(self.file_wl_measured)
            wlmax = read_2col_file(self.file_wlmax)
            wl_meas = wl_meas[:len(self.wvn)]
            self.corr = wl_correction_from_true_and_measured(
                wl_meas, self.wvn, wlmax,
                smooth_win=15, poly_deg=8, center_wavelength=860.0
            )
            self._preview_curve(self.corr, "WL Correction Factor")
            self.btn_ok.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"WL correction failed:\n{e}")

    # ---------------- NIST ----------------
    def _ui_nist_inputs(self):
        self.mode = "NIST"
        self._clear_q_area()
        self.label_title.setText("NIST/SRM Correction Inputs")

        btn_srm = QPushButton("Load SRM Measured Spectrum (vector)")
        btn_srm.clicked.connect(self._pick_srm)

        btn_coeffs = QPushButton("Load NIST Polynomial Coefficients")
        btn_coeffs.clicked.connect(self._pick_coeffs)

        btn_compute = QPushButton("Compute NIST Correction")
        btn_compute.clicked.connect(self._compute_nist_corr)

        self.q_layout.addWidget(btn_srm)
        self.q_layout.addWidget(btn_coeffs)
        self.actions.addWidget(btn_compute)

        # Back
        btn_back = QPushButton("Back")
        btn_back.clicked.connect(self._choose_method)
        self.actions.addWidget(btn_back)

    def _pick_srm(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select SRM Measured Spectrum",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return
        try:
            _ = read_vector_file(fp)
            self.file_srm_measured = fp
            QMessageBox.information(self, "Loaded", "SRM spectrum loaded.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read: {e}")

    def _pick_coeffs(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select NIST Polynomial Coefficients",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return
        try:
            _ = read_coeffs_file(fp)
            self.file_coeffs = fp
            QMessageBox.information(self, "Loaded", "Coefficients loaded.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read: {e}")

    def _compute_nist_corr(self):
        if not self.file_srm_measured or not self.file_coeffs:
            QMessageBox.warning(self, "Missing", "Load SRM spectrum and coefficients first.")
            return
        try:
            srm = read_vector_file(self.file_srm_measured)
            coeffs = read_coeffs_file(self.file_coeffs)
            if self.wvn is not None and len(self.wvn) == len(srm):
                x_axis = self.wvn
                center_val = 1100.0
            else:
                x_axis = np.arange(len(srm), dtype=float)
                center_val = len(srm) // 2

            self.corr = nist_correction_from_srm(
                srm, x_axis, coeffs,
                smooth_win=9, center_wvn=center_val, baseline_slice=slice(10, 25)
            )
            self._preview_curve(self.corr, "NIST/SRM Correction Factor")
            self.btn_ok.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"NIST correction failed:\n{e}")

    # ---------------- Visualization ----------------
    def _preview_curve(self, corr, title="Correction Factor"):
        self.ax.clear()
        if self.wvn is not None and len(self.wvn) == len(corr):
            x_axis = 10e-7 / self.wvn
            self.ax.plot(x_axis, corr)
            self.ax.set_xlabel("Wavelength (unit from 10e-7/Wvn)")
        else:
            self.ax.plot(np.arange(len(corr)), corr)
            self.ax.set_xlabel("Index")
        self.ax.set_ylabel("Correction")
        self.ax.set_title(title)
        self.canvas.draw()

    # ---------------- Auto-save at Finish ----------------
    def _on_finish(self):
        """Auto-save correction result when finishing."""
        if self.corr is None:
            QMessageBox.warning(self, "No Data", "No correction factor computed or loaded.")
            self.result = "Cancelled"
            self.reject()
            return

        # auto filename based on mode
        if self.mode == "WL":
            default_name = "wl_correction_result.txt"
        elif self.mode == "NIST":
            default_name = "nist_correction_result.txt"
        else:
            default_name = "existing_correction_result.txt"

        fp, _ = QFileDialog.getSaveFileName(
            self, "Save Correction Factor As",
            default_name,
            "Text Files (*.txt);;All Files (*)"
        )
        if not fp:
            fp = os.path.join(os.getcwd(), default_name)
            QMessageBox.information(self, "Auto Save", f"No path selected. Saving to:\n{fp}")

        try:
            np.savetxt(fp, self.corr.reshape(-1, 1), delimiter=",", header="Correction", comments='')
            QMessageBox.information(self, "Saved", f"Correction file saved:\n{fp}")
            self.result = "CorrComputed"
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
            self.result = "Cancelled"
            self.reject()


# ---------- Quick test ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = SpectrumCorrectionProcessUI()
    if dlg.exec_():
        print("Result:", dlg.result)
        if dlg.corr is not None:
            print("Correction Length:", len(dlg.corr))
    else:
        print("Cancelled")
