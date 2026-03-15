# UI_SRCF.py
# -*- coding: utf-8 -*-

"""
Spectral Response Correction Factor UI

Qt dialog for spectral response correction workflow with complete functionality:
  - Select correction method: White-Light, NIST, or Load Existing Factor
  - Upload required input files based on method
  - Compute correction factor
  - Upload raw spectrum to correct
  - Display comparison chart (original vs corrected)
  - Save correction factor and corrected spectrum

Relies on utils.WLCorrection for algorithms and file IO.

Exposes:
    dlg.result: str ("UseExistingFactor" | "CorrComputed" | "WvnUploaded" | "RequireXAxisCalibration" | "Cancelled")
    dlg.wvn:    np.ndarray or None
    dlg.corr:   np.ndarray or None
    dlg.corrected_spectrum: np.ndarray or None
"""

import sys
import os
import numpy as np
from scipy.io import loadmat
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QMessageBox, QFileDialog, QFrame, QGroupBox, QGridLayout,
    QComboBox, QSpinBox, QDoubleSpinBox, QSplitter, QWidget, QStatusBar,
    QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# Import core functions from utils module
from utils.WLCorrection import (
    read_vector_file, read_2col_file,
    wl_correction_from_true_and_measured, nist_correction_from_srm
)
from UI_utils.UI_theme import get_stylesheet, Colors, Fonts


class SRCF_UI(QDialog):
    """Spectral Response Correction Factor Dialog with full workflow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spectral Response Correction Factor")
        # Enable minimize and maximize buttons
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self.setMinimumSize(600, 450)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1100, int(screen.width() * 0.9)), min(750, int(screen.height() * 0.9)))
        self.move(screen.center() - self.rect().center())
        # Apply unified dark theme
        self.setStyleSheet(get_stylesheet())

        # ============ Data and State ============
        self.result = None
        self.wvn = None  # Wavenumber array from calibration
        self.laser_wavelength = 785.0  # Default, overwritten from calibration file
        self.corr = None  # Correction factor array
        self.mode = "WL"  # "WL", "NIST", "EXIST"

        # Raw spectrum data
        self.raw_spectrum = None
        self.raw_spectrum_file = None

        # Corrected spectrum
        self.corrected_spectrum = None

        # Files for WL method
        self.file_wl_measured = None
        self.wl_measured_data = None
        self.file_wlmax = None
        self.wlmax_data = None

        # Files for NIST method
        self.file_srm_measured = None
        self.srm_data = None

        # Calibration file
        self.file_wvn_mat = None

        # Build UI
        self._build_ui()
        self._update_mode_ui()

    # ============================================================
    # UI Construction
    # ============================================================

    def _build_ui(self):
        """Build the main UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Title
        title = QLabel("Spectral Response Correction Factor")
        title.setFont(QFont("Segoe UI", Fonts.SIZE_XL, QFont.Bold))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; padding: 6px;")
        title.setAlignment(Qt.AlignCenter)
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        main_layout.addWidget(title, 0)

        # Create splitter for left panel and right chart
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ============ Left Panel - Controls (wrapped in ScrollArea) ============
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(250)
        left_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #444;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(6)

        # ---------- Step 1: Method Selection ----------
        method_group = QGroupBox("Step 1: Select Correction Method")
        method_layout = QHBoxLayout(method_group)

        self.combo_method = QComboBox()
        self.combo_method.addItems([
            "White-Light Correction",
            "NIST/SRM Correction",
            "Load Existing Factor"
        ])
        self.combo_method.currentIndexChanged.connect(self._on_method_changed)
        method_layout.addWidget(QLabel("Method:"))
        method_layout.addWidget(self.combo_method)
        method_layout.addStretch()
        left_layout.addWidget(method_group)

        # ---------- Step 2: Calibration (for WL and NIST) ----------
        self.calib_group = QGroupBox("Step 2: X-Axis Calibration")
        calib_layout = QVBoxLayout(self.calib_group)

        calib_row = QHBoxLayout()
        self.btn_load_calib = QPushButton("Load Calibration (.mat)")
        self.btn_load_calib.clicked.connect(self._load_calibration)
        self.lbl_calib_status = QLabel("Not loaded")
        self.lbl_calib_status.setStyleSheet("color: #888;")
        calib_row.addWidget(self.btn_load_calib)
        calib_row.addWidget(self.lbl_calib_status)
        calib_row.addStretch()
        calib_layout.addLayout(calib_row)
        left_layout.addWidget(self.calib_group)

        # ---------- Step 3: Method Inputs ----------
        self.inputs_group = QGroupBox("Step 3: Method Inputs")
        self.inputs_layout = QVBoxLayout(self.inputs_group)

        # --- WL Inputs Container ---
        self.wl_inputs_widget = QWidget()
        wl_layout = QVBoxLayout(self.wl_inputs_widget)
        wl_layout.setContentsMargins(0, 0, 0, 0)

        # Measured WL Spectrum
        wl_meas_row = QHBoxLayout()
        self.btn_wl_measured = QPushButton("Load Measured WL Spectrum")
        self.btn_wl_measured.clicked.connect(self._load_wl_measured)
        self.lbl_wl_measured = QLabel("Not loaded")
        self.lbl_wl_measured.setStyleSheet("color: #888;")
        wl_meas_row.addWidget(self.btn_wl_measured)
        wl_meas_row.addWidget(self.lbl_wl_measured)
        wl_meas_row.addStretch()
        wl_layout.addLayout(wl_meas_row)

        # True WL Reference
        wl_ref_row = QHBoxLayout()
        self.btn_wl_ref = QPushButton("Load True WL Reference (2-col)")
        self.btn_wl_ref.clicked.connect(self._load_wl_reference)
        self.lbl_wl_ref = QLabel("Not loaded")
        self.lbl_wl_ref.setStyleSheet("color: #888;")
        wl_ref_row.addWidget(self.btn_wl_ref)
        wl_ref_row.addWidget(self.lbl_wl_ref)
        wl_ref_row.addStretch()
        wl_layout.addLayout(wl_ref_row)

        # WL Parameters
        wl_params = QGridLayout()
        wl_params.addWidget(QLabel("Smooth Window:"), 0, 0)
        self.spin_wl_smooth = QSpinBox()
        self.spin_wl_smooth.setRange(3, 51)
        self.spin_wl_smooth.setSingleStep(2)
        self.spin_wl_smooth.setValue(15)
        wl_params.addWidget(self.spin_wl_smooth, 0, 1)

        wl_params.addWidget(QLabel("Poly Order:"), 0, 2)
        self.spin_wl_poly = QSpinBox()
        self.spin_wl_poly.setRange(1, 15)
        self.spin_wl_poly.setValue(8)
        wl_params.addWidget(self.spin_wl_poly, 0, 3)

        wl_params.addWidget(QLabel("Center λ (nm):"), 1, 0)
        self.spin_wl_center = QDoubleSpinBox()
        self.spin_wl_center.setRange(400, 1200)
        self.spin_wl_center.setValue(860.0)
        wl_params.addWidget(self.spin_wl_center, 1, 1)

        wl_layout.addLayout(wl_params)
        self.inputs_layout.addWidget(self.wl_inputs_widget)

        # --- NIST Inputs Container ---
        self.nist_inputs_widget = QWidget()
        nist_layout = QVBoxLayout(self.nist_inputs_widget)
        nist_layout.setContentsMargins(0, 0, 0, 0)

        # SRM Measured Spectrum
        srm_row = QHBoxLayout()
        self.btn_srm = QPushButton("Load SRM Measured Spectrum")
        self.btn_srm.clicked.connect(self._load_srm)
        self.lbl_srm = QLabel("Not loaded")
        self.lbl_srm.setStyleSheet("color: #888;")
        srm_row.addWidget(self.btn_srm)
        srm_row.addWidget(self.lbl_srm)
        srm_row.addStretch()
        nist_layout.addLayout(srm_row)

        # NIST Coefficients - hardcoded, show info label only
        coeffs_info = QLabel("✓ NIST Polynomial Coefficients (built-in)")
        coeffs_info.setStyleSheet("color: #28a745; font-style: italic;")
        nist_layout.addWidget(coeffs_info)

        # NIST Parameters
        nist_params = QGridLayout()
        nist_params.addWidget(QLabel("Smooth Window:"), 0, 0)
        self.spin_nist_smooth = QSpinBox()
        self.spin_nist_smooth.setRange(3, 51)
        self.spin_nist_smooth.setSingleStep(2)
        self.spin_nist_smooth.setValue(9)
        nist_params.addWidget(self.spin_nist_smooth, 0, 1)

        nist_params.addWidget(QLabel("Center Wvn:"), 0, 2)
        self.spin_nist_center = QDoubleSpinBox()
        self.spin_nist_center.setRange(100, 4000)
        self.spin_nist_center.setValue(1100.0)
        nist_params.addWidget(self.spin_nist_center, 0, 3)

        nist_params.addWidget(QLabel("Baseline Start:"), 1, 0)
        self.spin_nist_bl_start = QSpinBox()
        self.spin_nist_bl_start.setRange(0, 100)
        self.spin_nist_bl_start.setValue(10)
        nist_params.addWidget(self.spin_nist_bl_start, 1, 1)

        nist_params.addWidget(QLabel("Baseline End:"), 1, 2)
        self.spin_nist_bl_end = QSpinBox()
        self.spin_nist_bl_end.setRange(1, 200)
        self.spin_nist_bl_end.setValue(25)
        nist_params.addWidget(self.spin_nist_bl_end, 1, 3)

        nist_layout.addLayout(nist_params)
        self.inputs_layout.addWidget(self.nist_inputs_widget)

        # --- Existing Factor Input ---
        self.exist_inputs_widget = QWidget()
        exist_layout = QVBoxLayout(self.exist_inputs_widget)
        exist_layout.setContentsMargins(0, 0, 0, 0)

        exist_row = QHBoxLayout()
        self.btn_load_exist = QPushButton("Load Existing Correction Factor")
        self.btn_load_exist.clicked.connect(self._load_existing_factor)
        self.lbl_exist = QLabel("Not loaded")
        self.lbl_exist.setStyleSheet("color: #888;")
        exist_row.addWidget(self.btn_load_exist)
        exist_row.addWidget(self.lbl_exist)
        exist_row.addStretch()
        exist_layout.addLayout(exist_row)

        self.inputs_layout.addWidget(self.exist_inputs_widget)
        left_layout.addWidget(self.inputs_group)

        # ---------- Compute Button ----------
        self.btn_compute = QPushButton("Compute Correction Factor")
        self.btn_compute.setStyleSheet(
            "background-color: #4C8BF5; color: white; font-weight: bold; padding: 8px;"
        )
        self.btn_compute.clicked.connect(self._compute_correction)
        left_layout.addWidget(self.btn_compute)

        # ---------- Step 4: Raw Spectrum ----------
        raw_group = QGroupBox("Step 4: Upload Raw Spectrum to Correct")
        raw_layout = QVBoxLayout(raw_group)

        raw_row = QHBoxLayout()
        self.btn_load_raw = QPushButton("Load Raw Spectrum")
        self.btn_load_raw.clicked.connect(self._load_raw_spectrum)
        self.lbl_raw_status = QLabel("Not loaded")
        self.lbl_raw_status.setStyleSheet("color: #888;")
        raw_row.addWidget(self.btn_load_raw)
        raw_row.addWidget(self.lbl_raw_status)
        raw_row.addStretch()
        raw_layout.addLayout(raw_row)
        left_layout.addWidget(raw_group)

        # ---------- Apply Correction Button ----------
        self.btn_apply = QPushButton("Apply Correction to Raw Spectrum")
        self.btn_apply.setStyleSheet(
            "background-color: #28a745; color: white; font-weight: bold; padding: 8px;"
        )
        self.btn_apply.clicked.connect(self._apply_correction)
        self.btn_apply.setEnabled(False)
        left_layout.addWidget(self.btn_apply)

        # ---------- Step 5: Save Results ----------
        save_group = QGroupBox("Step 5: Save Results")
        save_layout = QHBoxLayout(save_group)

        self.btn_save_corr = QPushButton("Save Correction Factor")
        self.btn_save_corr.clicked.connect(self._save_correction_factor)
        self.btn_save_corr.setEnabled(False)

        self.btn_save_spectrum = QPushButton("Save Corrected Spectrum")
        self.btn_save_spectrum.clicked.connect(self._save_corrected_spectrum)
        self.btn_save_spectrum.setEnabled(False)

        save_layout.addWidget(self.btn_save_corr)
        save_layout.addWidget(self.btn_save_spectrum)
        left_layout.addWidget(save_group)

        # ---------- Bottom Buttons ----------
        bottom_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        self.btn_ok = QPushButton("Finish")
        self.btn_ok.setStyleSheet("background-color: #4C8BF5; color: white;")
        self.btn_ok.clicked.connect(self._on_finish)

        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_cancel)
        bottom_layout.addWidget(self.btn_ok)
        left_layout.addLayout(bottom_layout)

        # Set left_widget as the scroll area's widget
        left_scroll.setWidget(left_widget)

        # ============ Right Panel - Charts ============
        right_widget = QWidget()
        right_widget.setMinimumWidth(250)
        right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)

        # Matplotlib figure with two subplots (dark theme)
        self.fig = Figure(figsize=(6, 5), dpi=100)
        self.fig.set_facecolor(Colors.BG_SECONDARY)
        self.ax_corr = self.fig.add_subplot(211)
        self.ax_compare = self.fig.add_subplot(212)
        self._style_axes()
        self.fig.tight_layout(pad=2.5)

        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setMinimumSize(200, 200)
        # Override sizeHint to prevent canvas from dominating splitter
        self.canvas.sizeHint = lambda: QSize(400, 300)
        self.canvas.minimumSizeHint = lambda: QSize(200, 200)
        self.canvas.draw()
        self.canvas.mpl_connect('resize_event', self._on_canvas_resize)
        self.toolbar = NavigationToolbar(self.canvas, self)

        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)

        # Add widgets to splitter
        splitter.addWidget(left_scroll)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)  # Left panel stretch factor
        splitter.setStretchFactor(1, 2)  # Right panel stretch factor (larger)
        splitter.setSizes([350, 650])

        main_layout.addWidget(splitter, 1)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready. Select a correction method to begin.")
        main_layout.addWidget(self.status_bar)

    def _canvas_font_sizes(self):
        """Calculate font sizes based on canvas width."""
        w = self.canvas.width() if hasattr(self, 'canvas') else 400
        title = max(9, min(16, int(w / 40)))
        label = max(8, min(13, int(w / 50)))
        tick = max(7, min(12, int(w / 55)))
        legend = max(7, min(11, int(w / 55)))
        return title, label, tick, legend

    def _on_canvas_resize(self, event):
        """Re-apply font sizes when canvas is resized."""
        fs_title, fs_label, fs_tick, fs_legend = self._canvas_font_sizes()
        for ax in [self.ax_corr, self.ax_compare]:
            ax.title.set_fontsize(fs_title)
            ax.xaxis.label.set_fontsize(fs_label)
            ax.yaxis.label.set_fontsize(fs_label)
            ax.tick_params(labelsize=fs_tick)
            legend = ax.get_legend()
            if legend:
                for text in legend.get_texts():
                    text.set_fontsize(fs_legend)
        self.fig.tight_layout(pad=2.5)
        self.canvas.draw_idle()

    def _style_axes(self):
        """Apply dark theme styling to matplotlib axes."""
        fs_title, _, fs_tick, _ = self._canvas_font_sizes()
        for ax in [self.ax_corr, self.ax_compare]:
            ax.set_facecolor(Colors.BG_TERTIARY)
            ax.grid(True, alpha=0.2, linestyle='--', color=Colors.BORDER)
            ax.tick_params(labelsize=fs_tick, colors=Colors.TEXT_SECONDARY)
            for spine in ax.spines.values():
                spine.set_color(Colors.BORDER)
        self.ax_corr.set_title("Correction Factor", fontsize=fs_title, fontweight='bold', color=Colors.TEXT_PRIMARY)
        self.ax_compare.set_title("Spectrum Comparison", fontsize=fs_title, fontweight='bold', color=Colors.TEXT_PRIMARY)

    # ============================================================
    # Method Selection
    # ============================================================

    def _on_method_changed(self, index):
        """Handle method selection change."""
        methods = ["WL", "NIST", "EXIST"]
        self.mode = methods[index]
        self._update_mode_ui()

    def _update_mode_ui(self):
        """Update UI visibility based on selected method."""
        index = self.combo_method.currentIndex()

        # Show/hide calibration group (for WL and NIST, not for Load Existing)
        self.calib_group.setVisible(index in [0, 1])

        # Show/hide input widgets
        self.wl_inputs_widget.setVisible(index == 0)
        self.nist_inputs_widget.setVisible(index == 1)
        self.exist_inputs_widget.setVisible(index == 2)

        # Update compute button
        if index == 0:
            self.btn_compute.setText("Compute WL Correction Factor")
            self.btn_compute.setVisible(True)
            self.mode = "WL"
        elif index == 1:
            self.btn_compute.setText("Compute NIST Correction Factor")
            self.btn_compute.setVisible(True)
            self.mode = "NIST"
        else:
            self.btn_compute.setVisible(False)
            self.mode = "EXIST"

    # ============================================================
    # File Loading Functions
    # ============================================================

    def _load_calibration(self):
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
                    if "Wavelength" in cal_struct.dtype.names:
                        self.laser_wavelength = float(cal_struct["Wavelength"][0, 0].flatten()[0])
                    self.file_wvn_mat = fp
                    self.result = "WvnUploaded"
                    self.lbl_calib_status.setText(f"✓ Loaded ({len(self.wvn)} points)")
                    self.lbl_calib_status.setStyleSheet("color: #28a745;")
                    self.status_bar.showMessage(
                        f"Calibration loaded: {len(self.wvn)} points, laser {self.laser_wavelength:.1f} nm"
                    )
                    return True

            QMessageBox.warning(self, "Invalid File", "Missing Cal['Wvn'] in .mat file.")
            return False

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return False

    def _load_wl_measured(self):
        """Load measured White-Light spectrum."""
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select Measured White-Light Spectrum",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return

        try:
            self.wl_measured_data = read_vector_file(fp)
            self.file_wl_measured = fp
            self.lbl_wl_measured.setText(f"✓ Loaded ({len(self.wl_measured_data)} pts)")
            self.lbl_wl_measured.setStyleSheet("color: #28a745;")
            self.status_bar.showMessage(f"Measured WL loaded: {os.path.basename(fp)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read: {e}")

    def _load_wl_reference(self):
        """Load true WL reference file (2-column: wavelength, intensity)."""
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select True WL Reference (wavelength, intensity)",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return

        try:
            self.wlmax_data = read_2col_file(fp)
            self.file_wlmax = fp
            self.lbl_wl_ref.setText(f"✓ Loaded ({len(self.wlmax_data)} pts)")
            self.lbl_wl_ref.setStyleSheet("color: #28a745;")
            self.status_bar.showMessage(f"True WL reference loaded: {os.path.basename(fp)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read: {e}")

    def _load_srm(self):
        """Load SRM measured spectrum."""
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select SRM Measured Spectrum",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return

        try:
            self.srm_data = read_vector_file(fp)
            self.file_srm_measured = fp
            self.lbl_srm.setText(f"✓ Loaded ({len(self.srm_data)} pts)")
            self.lbl_srm.setStyleSheet("color: #28a745;")
            self.status_bar.showMessage(f"SRM spectrum loaded: {os.path.basename(fp)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read: {e}")

    def _load_existing_factor(self):
        """Load an existing correction factor."""
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select Existing Spectral Response Factor",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return

        try:
            corr = read_vector_file(fp)
            self.corr = corr  # Keep as (N, 1) column vector
            self.mode = "EXIST"
            self.result = "UseExistingFactor"
            self.lbl_exist.setText(f"✓ Loaded ({len(self.corr)} pts)")
            self.lbl_exist.setStyleSheet("color: #28a745;")
            self.btn_save_corr.setEnabled(True)
            self._update_apply_button()
            self._plot_correction_factor()
            self.status_bar.showMessage(
                f"Existing correction factor loaded: {len(self.corr)} points"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load: {e}")

    def _load_raw_spectrum(self):
        """Load raw spectrum to be corrected."""
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select Raw Spectrum to Correct",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not fp:
            return

        try:
            data = read_vector_file(fp)
            self.raw_spectrum = data  # Keep as (N, 1) column vector
            self.raw_spectrum_file = fp
            self.lbl_raw_status.setText(f"✓ Loaded ({len(self.raw_spectrum)} pts)")
            self.lbl_raw_status.setStyleSheet("color: #28a745;")
            self._update_apply_button()
            self.status_bar.showMessage(
                f"Raw spectrum loaded: {os.path.basename(fp)} ({len(self.raw_spectrum)} points)"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load raw spectrum: {e}")

    # ============================================================
    # Correction Computation
    # ============================================================

    def _compute_correction(self):
        """Compute correction factor based on selected method."""
        if self.mode == "WL":
            self._compute_wl_correction()
        elif self.mode == "NIST":
            self._compute_nist_correction()

    def _compute_wl_correction(self):
        """Compute White-Light correction factor."""
        # Validation
        if self.wvn is None:
            QMessageBox.warning(self, "Missing", "Please load Calibration (.mat) first.")
            return
        if self.wl_measured_data is None:
            QMessageBox.warning(self, "Missing", "Please load Measured WL spectrum.")
            return
        if self.wlmax_data is None:
            QMessageBox.warning(self, "Missing", "Please load True WL reference.")
            return

        try:
            # Truncate measured data to match calibration length
            wl_meas = self.wl_measured_data[:len(self.wvn)]

            # Get parameters from UI
            smooth_win = self.spin_wl_smooth.value()
            poly_order = self.spin_wl_poly.value()
            center_wl = self.spin_wl_center.value()

            # Compute correction
            self.corr = wl_correction_from_true_and_measured(
                wl_meas, self.wvn, self.wlmax_data,
                smooth_window=smooth_win,
                poly_order=poly_order,
                center_wavelength=center_wl,
                laser_wavelength=self.laser_wavelength
            )

            self.result = "CorrComputed"
            self.btn_save_corr.setEnabled(True)
            self._update_apply_button()
            self._plot_correction_factor()
            self.status_bar.showMessage(
                f"WL Correction computed successfully ({len(self.corr)} points)"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"WL correction failed:\n{e}")

    def _compute_nist_correction(self):
        """Compute NIST/SRM correction factor."""
        # Validation
        if self.wvn is None:
            QMessageBox.warning(self, "Missing", "Please load Calibration (.mat) first.")
            return
        if self.srm_data is None:
            QMessageBox.warning(self, "Missing", "Please load SRM measured spectrum.")
            return

        try:
            # Truncate SRM data to match calibration length
            srm_meas = self.srm_data[:len(self.wvn)]

            # Get parameters from UI
            smooth_win = self.spin_nist_smooth.value()
            center_wvn = self.spin_nist_center.value()
            bl_start = self.spin_nist_bl_start.value()
            bl_end = self.spin_nist_bl_end.value()

            # Compute correction (coeffs are hardcoded in the function)
            self.corr = nist_correction_from_srm(
                srm_meas, self.wvn, None,
                smooth_window=smooth_win,
                center_wvn=center_wvn,
                baseline_range=(bl_start, bl_end)
            )

            self.result = "CorrComputed"
            self.btn_save_corr.setEnabled(True)
            self._update_apply_button()
            self._plot_correction_factor()
            self.status_bar.showMessage(
                f"NIST Correction computed successfully ({len(self.corr)} points)"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"NIST correction failed:\n{e}")

    # ============================================================
    # Apply Correction
    # ============================================================

    def _update_apply_button(self):
        """Enable apply button if both correction and raw spectrum are ready."""
        can_apply = self.corr is not None and self.raw_spectrum is not None
        self.btn_apply.setEnabled(can_apply)

    def _apply_correction(self):
        """Apply correction factor to raw spectrum."""
        if self.corr is None:
            QMessageBox.warning(self, "Missing", "No correction factor available.")
            return
        if self.raw_spectrum is None:
            QMessageBox.warning(self, "Missing", "No raw spectrum loaded.")
            return

        try:
            # Match lengths
            min_len = min(len(self.corr), len(self.raw_spectrum))
            corr_truncated = self.corr[:min_len]
            raw_truncated = self.raw_spectrum[:min_len]

            # Normalize correction factor
            # Use index 199 onwards for normalization (or available range)
            norm_start = min(199, min_len - 1)
            norm_value = np.mean(corr_truncated[norm_start:])
            if norm_value == 0:
                norm_value = 1.0
            corr_normalized = corr_truncated / norm_value

            # Apply correction: corrected = raw * correction_factor
            self.corrected_spectrum = raw_truncated * corr_normalized

            self.btn_save_spectrum.setEnabled(True)
            self._plot_comparison()
            self.status_bar.showMessage("Correction applied successfully. Ready to save.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply correction:\n{e}")

    # ============================================================
    # Plotting
    # ============================================================

    def _plot_correction_factor(self):
        """Plot the correction factor."""
        fs_title, fs_label, _, _ = self._canvas_font_sizes()
        self.ax_corr.clear()

        if self.corr is None:
            self.canvas.draw()
            return

        if self.wvn is not None and len(self.wvn) == len(self.corr):
            wavelength = 1e7 / (1e7 / self.laser_wavelength - self.wvn)
            self.ax_corr.plot(wavelength, self.corr, 'b-', linewidth=1.5)
            self.ax_corr.set_xlabel("Wavelength (nm)", fontsize=fs_label)
        else:
            self.ax_corr.plot(np.arange(len(self.corr)), self.corr, 'b-', linewidth=1.5)
            self.ax_corr.set_xlabel("Index", fontsize=fs_label)

        self.ax_corr.set_ylabel("Correction Factor", fontsize=fs_label)
        self.ax_corr.set_title("Spectral Response Correction Factor", fontsize=fs_title, fontweight='bold')
        self.ax_corr.grid(True, alpha=0.3)

        self.fig.tight_layout(pad=3.0)
        self.canvas.draw()

    def _plot_comparison(self):
        """Plot comparison between original and corrected spectrum."""
        fs_title, fs_label, _, fs_legend = self._canvas_font_sizes()
        self.ax_compare.clear()

        if self.raw_spectrum is None:
            self.canvas.draw()
            return

        min_len = len(self.raw_spectrum)
        if self.corrected_spectrum is not None:
            min_len = min(len(self.raw_spectrum), len(self.corrected_spectrum))

        if self.wvn is not None and len(self.wvn) >= min_len:
            x_axis = self.wvn[:min_len]
            xlabel = "Wavenumber (cm⁻¹)"
        else:
            x_axis = np.arange(min_len)
            xlabel = "Index"

        self.ax_compare.plot(
            x_axis, self.raw_spectrum[:min_len],
            'b-', linewidth=1, alpha=0.7, label='Original'
        )

        if self.corrected_spectrum is not None:
            self.ax_compare.plot(
                x_axis, self.corrected_spectrum[:min_len],
                'r-', linewidth=1, alpha=0.7, label='Corrected'
            )

        self.ax_compare.set_xlabel(xlabel, fontsize=fs_label)
        self.ax_compare.set_ylabel("Intensity", fontsize=fs_label)
        self.ax_compare.set_title("Original vs Corrected Spectrum", fontsize=fs_title, fontweight='bold')
        self.ax_compare.legend(loc='best', fontsize=fs_legend)
        self.ax_compare.grid(True, alpha=0.3)

        self.fig.tight_layout(pad=3.0)
        self.canvas.draw()

    # ============================================================
    # Save Functions
    # ============================================================

    def _save_correction_factor(self):
        """Save the correction factor to file."""
        if self.corr is None:
            QMessageBox.warning(self, "No Data", "No correction factor to save.")
            return

        # Default filename based on mode
        default_names = {
            "WL": "wl_correction_factor.txt",
            "NIST": "nist_correction_factor.txt",
            "EXIST": "correction_factor.txt"
        }
        default_name = default_names.get(self.mode, "correction_factor.txt")

        fp, _ = QFileDialog.getSaveFileName(
            self, "Save Correction Factor",
            default_name,
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)"
        )

        if not fp:
            return

        try:
            np.savetxt(
                fp, self.corr.reshape(-1, 1),
                delimiter=","
            )
            self.status_bar.showMessage(f"Correction factor saved: {fp}")
            QMessageBox.information(self, "Saved", f"Correction factor saved to:\n{fp}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def _save_corrected_spectrum(self):
        """Save the corrected spectrum to file."""
        if self.corrected_spectrum is None:
            QMessageBox.warning(self, "No Data", "No corrected spectrum to save.")
            return

        # Generate default filename
        default_name = "corrected_spectrum.txt"
        if self.raw_spectrum_file:
            base = os.path.splitext(os.path.basename(self.raw_spectrum_file))[0]
            default_name = f"{base}_corrected.txt"

        fp, _ = QFileDialog.getSaveFileName(
            self, "Save Corrected Spectrum",
            default_name,
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)"
        )

        if not fp:
            return

        try:
            min_len = len(self.corrected_spectrum)

            # Save with wavenumber if available
            if self.wvn is not None and len(self.wvn) >= min_len:
                data = np.column_stack((self.wvn[:min_len], self.corrected_spectrum))
                header = "Wavenumber,Corrected_Intensity"
            else:
                data = self.corrected_spectrum.reshape(-1, 1)
                header = "Corrected_Intensity"

            np.savetxt(fp, data, delimiter=",")
            self.status_bar.showMessage(f"Corrected spectrum saved: {fp}")
            QMessageBox.information(self, "Saved", f"Corrected spectrum saved to:\n{fp}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    # ============================================================
    # Dialog Actions
    # ============================================================

    def _on_finish(self):
        """Handle finish button click."""
        if self.corr is None:
            reply = QMessageBox.question(
                self, "No Correction",
                "No correction factor computed. Close anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.result = "Cancelled"
                self.reject()
            return

        self.result = "CorrComputed"
        self.accept()


# ============================================================
# Quick Test
# ============================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = SRCF_UI()
    if dlg.exec_():
        print("Result:", dlg.result)
        if dlg.corr is not None:
            print("Correction Length:", len(dlg.corr))
        if dlg.corrected_spectrum is not None:
            print("Corrected Spectrum Length:", len(dlg.corrected_spectrum))
    else:
        print("Cancelled")
