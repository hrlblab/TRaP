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
    """
    Dialog (UI only). Use utils.WLCorrection for computation.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spectrum Correction Process")
        self.setFixedSize(720, 520)

        # Flow state and data
        self.result = None
        self.wvn = None           # X-axis calibration (cm^-1)
        self.corr = None          # Correction factor
        self.mode = None          # "WL" | "NIST" | "EXIST"

        # Files
        self.file_wl_measured = None
        self.file_srm_measured = None
        self.file_wlmax = None
        self.file_coeffs = None
        self.file_wvn_mat = None

        self._build_ui()
        self._choose_method()  # entry page

    # ---------- UI building ----------
    def _build_ui(self):
        self.layout = QVBoxLayout(self)

        self.label_title = QLabel("", self)
        self.layout.addWidget(self.label_title)

        self.q_area = QFrame(self)
        self.q_layout = QVBoxLayout(self.q_area)
        self.layout.addWidget(self.q_area)

        self.actions = QHBoxLayout()
        self.layout.addLayout(self.actions)

        # Plot
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

    # ---------- robust layout clear ----------
    def _clear_layout(self, layout: QLayout):
        """Recursively remove all widgets and sub-layouts from a layout."""
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
        # do not delete 'layout' itself; it belongs to parent

    def _clear_q_area(self):
        self._clear_layout(self.q_layout)
        self._clear_layout(self.actions)

    # ---------- Entry: choose method ----------
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
        btn_nist.clicked.connect(self._ui_nist_inputs)  # NIST does NOT require Wvn

        row.addWidget(btn_exist)
        row.addWidget(btn_wl)
        row.addWidget(btn_nist)
        self.q_layout.addLayout(row)

    # ---------- Common: Wvn loader for WL ----------
    def _load_wvn_mat(self):
        """Open .mat and load Cal['Wvn'] vector."""
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select X Axis Calibration File",
            "", "MAT files (*.mat);;All Files (*)"
        )
        if not fp:
            QMessageBox.warning(self, "No File", "No file selected.")
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
                else:
                    QMessageBox.warning(self, "Invalid File", "Missing Cal['Wvn'].")
                    return False
            else:
                QMessageBox.warning(self, "Invalid File", "No 'Cal' struct in .mat.")
                return False
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return False

    def _ensure_wvn(self) -> bool:
        """WL must have Wvn; if absent, prompt to load or go back."""
        if self.wvn is not None:
            return True
        reply = QMessageBox.question(
            self, "X Axis Calibration Required",
            "White-Light correction requires Calibration (.mat with Cal['Wvn']). Do you have it?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok = self._load_wvn_mat()
            return ok
        else:
            QMessageBox.information(
                self, "Calibration Needed",
                "Please complete X-axis Calibration in the separate window, then save as .mat."
            )
            self.result = "RequireXAxisCalibration"
            # Return to method selector (do not close the dialog)
            self._choose_method()
            return False

    # ---------- Load existing factor ----------
    def _on_have_factor(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Existing Spectral Response Factor",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not file_path:
            QMessageBox.information(self, "Info", "No file selected.")
            return
        try:
            corr = read_vector_file(file_path)
            self.corr = corr.reshape(-1)
            self.mode = "EXIST"
            self.result = "UseExistingFactor"
            self.btn_ok.setEnabled(True)
            self._clear_q_area()
            self.label_title.setText("Loaded Existing Factor")
            self._preview_curve(self.corr, title="Correction Factor (index axis)")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load factor:\n{e}")

    # ---------- WL ----------
    def _precheck_then_wl(self):
        if not self._ensure_wvn():
            return
        self._ui_wl_inputs()

    def _ui_wl_inputs(self):
        """WL needs: Measured WL (vector) + True WL (two-column table)."""
        self.mode = "WL"
        self._clear_q_area()
        self.label_title.setText("White-Light Correction Inputs")

        btn_wl_meas = QPushButton("Load Measured WL Spectrum (vector)")
        btn_wl_meas.clicked.connect(self._pick_wl_measured)

        btn_wlmax = QPushButton("Load True WL reference (2 columns: wavelength, intensity)")
        btn_wlmax.clicked.connect(self._pick_wlmax)

        btn_compute = QPushButton("Compute WL Correction")
        btn_compute.clicked.connect(self._compute_wl_corr)

        self.q_layout.addWidget(btn_wl_meas)
        self.q_layout.addWidget(btn_wlmax)
        self.actions.addWidget(btn_compute)

        # Show hint of Wvn already loaded
        hint = QLabel(f"Calibration loaded: {len(self.wvn)} points.")
        hint.setStyleSheet("color:#8B8B8B;")
        self.q_layout.addWidget(hint)

        # Back button to method selector
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
            QMessageBox.information(self, "Loaded", f"Measured WL selected.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read WL: {e}")

    def _pick_wlmax(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select True WL 2-column Reference",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return
        try:
            _ = read_2col_file(fp)
            self.file_wlmax = fp
            QMessageBox.information(self, "Loaded", f"True WL table loaded.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read True WL: {e}")

    def _compute_wl_corr(self):
        if self.wvn is None:
            QMessageBox.warning(self, "Missing", "Please load Cal['Wvn'] first.")
            return
        if not self.file_wl_measured or not self.file_wlmax:
            QMessageBox.warning(self, "Missing", "Please load measured WL and True WL reference.")
            return
        try:
            wl_meas = read_vector_file(self.file_wl_measured)
            wlmax = read_2col_file(self.file_wlmax)

            if len(wl_meas) != len(self.wvn):
                if len(wl_meas) < len(self.wvn):
                    raise ValueError("Measured WL length must match Wvn length.")
                wl_meas = wl_meas[:len(self.wvn)]

            self.corr = wl_correction_from_true_and_measured(
                wl_meas, self.wvn, wlmax,
                smooth_win=15, poly_deg=8, center_wavelength=860.0
            )
            self._preview_curve(self.corr, title="WL Correction Factor vs Wavelength")
            self._offer_save_corr(default_name="wl_correction.txt")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"WL correction failed:\n{e}")

    # ---------- NIST ----------
    def _ui_nist_inputs(self):
        """
        NIST needs: SRM measured spectrum (vector) + polynomial coefficients.
        Calibration (Wvn) is NOT required; if present and length matches,
        we will prefer it as the x-axis; otherwise we use index axis (0..N-1).
        """
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

        # Back to method selector
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
            QMessageBox.critical(self, "Error", f"Failed to read SRM: {e}")

    def _pick_coeffs(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select Polynomial Coefficients",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return
        try:
            _ = read_coeffs_file(fp)
            self.file_coeffs = fp
            QMessageBox.information(self, "Loaded", "Coefficients loaded.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read coefficients: {e}")

    def _compute_nist_corr(self):
        if not self.file_srm_measured or not self.file_coeffs:
            QMessageBox.warning(self, "Missing", "Please load SRM spectrum and coefficients.")
            return
        try:
            srm = read_vector_file(self.file_srm_measured)
            coeffs = read_coeffs_file(self.file_coeffs)

            # If Wvn is available and matches length, use it as x-axis; otherwise use index axis.
            if self.wvn is not None and len(self.wvn) == len(srm):
                x_axis = self.wvn.astype(float)
                center_value = 1100.0  # conventional center in wavenumber
            else:
                x_axis = np.arange(len(srm), dtype=float)  # index axis
                center_value = float(len(srm) // 2)        # center at middle index

            self.corr = nist_correction_from_srm(
                srm, x_axis, coeffs,
                smooth_win=9, center_wvn=center_value, baseline_slice=slice(10, 25)
            )

            # Preview: if Wvn exists, draw in wavelength; else draw against index
            self._preview_curve(self.corr, title="NIST/SRM Correction Factor")
            self._offer_save_corr(default_name="nist_correction.txt")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"NIST correction failed:\n{e}")

    # ---------- Common helpers ----------
    def _preview_curve(self, corr, title="Correction Factor"):
        """Draw correction factor. If Wvn is present & aligned, plot against wavelength."""
        self.ax.clear()
        if self.wvn is not None and len(self.wvn) == len(corr):
            x_axis = 10e-7 / self.wvn  # same unit as WL preview
            self.ax.plot(x_axis, corr)
            self.ax.set_xlabel("Wavelength (unit from 10e-7/Wvn)")
        else:
            self.ax.plot(np.arange(len(corr)), corr)
            self.ax.set_xlabel("Index")
        self.ax.set_ylabel("Correction")
        self.ax.set_title(title)
        self.canvas.draw()
        self.btn_ok.setEnabled(True)

    def _offer_save_corr(self, default_name="correction.txt"):
        save_btn = QPushButton("Save Correction Factor")
        save_btn.clicked.connect(lambda: self._save_corr(default_name))
        # keep existing buttons (e.g., Back), only add save
        self.actions.addWidget(save_btn)

    def _save_corr(self, default_name: str):
        if self.corr is None:
            QMessageBox.warning(self, "No Data", "No correction factor to save.")
            return
        fp, _ = QFileDialog.getSaveFileName(
            self, "Save Correction Factor As",
            default_name,
            "Text/CSV (*.txt *.csv);;All Files (*)"
        )
        if not fp:
            return
        try:
            np.savetxt(fp, self.corr.reshape(-1, 1), delimiter=",", header="Correction", comments='')
            QMessageBox.information(self, "Saved", f"Saved to:\n{fp}")
            self.result = "CorrComputed"
            self.btn_ok.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def _on_finish(self):
        if self.result is None:
            self.result = "Cancelled"
        self.accept()


# Quick test
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = SpectrumCorrectionProcessUI()
    if dlg.exec_():
        print("Result:", dlg.result)
        if dlg.wvn is not None:
            print("Wvn Length:", len(dlg.wvn))
        if dlg.corr is not None:
            print("Corr Length:", len(dlg.corr))
    else:
        print("Cancelled")
