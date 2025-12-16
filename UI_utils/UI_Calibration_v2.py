# UI_Calibration_v2.py
# -*- coding: utf-8 -*-

"""
X-Axis Calibration UI v2

User-friendly calibration interface with:
  - Library reference value selection (checkboxes)
  - Dynamic peak count based on selection
  - Interactive peak selection on spectrum plot
  - Correct workflow: skip Acetaminophen when wavelength is known
  - Real-time status feedback

All UI text and comments in English.

Workflow:
  1. Select Neon-Argon library values
  2. Upload Neon spectrum and select peaks
  3. Choose: Known wavelength OR Acetaminophen estimation
     - If KNOWN: Enter wavelength -> Go directly to Step 5 (skip Step 4)
     - If UNKNOWN: Go to Step 4
  4. (Only if unknown) Upload Acetaminophen spectrum and select peaks
  5. Run calibration and save result
"""

import sys
import os
import numpy as np
import pandas as pd
from scipy.io import savemat

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QInputDialog, QProgressBar, QGroupBox,
    QSplitter, QFrame, QScrollArea, QCheckBox, QLineEdit, QSpinBox,
    QDoubleSpinBox, QTabWidget, QStatusBar, QSizePolicy, QStackedWidget
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from utils.Calibration_v2 import ReferenceLibrary, CalibrationProcessor


def load_spectrum_file(filepath: str) -> np.ndarray:
    """
    Load spectrum data from file.

    Supports: .txt, .csv, .xlsx files

    Returns:
        np.ndarray: Column vector (N, 1) for consistency across the workflow
    """
    ext = filepath.lower().split('.')[-1]
    if ext in ['txt', 'csv']:
        data = np.loadtxt(filepath)
    elif ext in ['xls', 'xlsx']:
        df = pd.read_excel(filepath, header=None)
        data = df.values.squeeze()
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    if data.ndim == 1:
        return data.reshape(-1, 1)
    elif data.ndim == 2:
        # If 2 columns, use the second as intensity
        if data.shape[1] >= 2:
            return data[:, 1].reshape(-1, 1)
        else:
            return data.reshape(-1, 1)
    else:
        raise ValueError("Invalid data format")


class SpectrumCanvas(FigureCanvas):
    """
    Interactive spectrum canvas for peak selection.

    Emits:
        peak_selected: Signal when a peak is selected
    """

    peak_selected = pyqtSignal(int, float)  # (pixel_position, intensity)

    def __init__(self, parent=None, width=8, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

        self.spectrum = None
        self.selected_points = []
        self.max_points = 0
        self.selection_enabled = False

        self.mpl_connect('button_press_event', self._on_click)

    def load_spectrum(self, spectrum: np.ndarray, title: str = "Spectrum"):
        """Load and display a spectrum."""
        self.spectrum = spectrum.flatten()
        # Normalize for display
        min_val = np.min(self.spectrum)
        max_val = np.max(self.spectrum)
        if max_val > min_val:
            normalized = (self.spectrum - min_val) / (max_val - min_val)
        else:
            normalized = self.spectrum

        self.ax.clear()
        self.ax.plot(normalized, 'b-', linewidth=0.8)
        self.ax.set_title(title)
        self.ax.set_xlabel("Pixel")
        self.ax.set_ylabel("Normalized Intensity")
        self.ax.grid(True, alpha=0.3)

        self.selected_points = []
        self.draw()

    def set_max_points(self, max_points: int):
        """Set maximum number of points that can be selected."""
        self.max_points = max_points

    def enable_selection(self, enabled: bool = True):
        """Enable or disable peak selection."""
        self.selection_enabled = enabled

    def clear_selection(self):
        """Clear all selected points."""
        self.selected_points = []
        if self.spectrum is not None:
            self.load_spectrum(self.spectrum, self.ax.get_title())

    def get_selected_points(self) -> list:
        """Get list of selected (pixel, intensity) tuples."""
        return self.selected_points.copy()

    def _on_click(self, event):
        """Handle mouse click for peak selection."""
        if not self.selection_enabled:
            return
        if event.inaxes != self.ax:
            return
        if self.spectrum is None:
            return
        if len(self.selected_points) >= self.max_points:
            return

        # Find nearest peak within a window
        clicked_x = int(round(event.xdata))
        window = 5
        start = max(0, clicked_x - window)
        end = min(len(self.spectrum), clicked_x + window + 1)
        local_region = self.spectrum[start:end]

        if len(local_region) == 0:
            return

        # Find local maximum
        local_max_idx = np.argmax(local_region)
        peak_x = start + local_max_idx
        peak_y = self.spectrum[peak_x]

        # Normalize y for display
        min_val = np.min(self.spectrum)
        max_val = np.max(self.spectrum)
        if max_val > min_val:
            peak_y_norm = (peak_y - min_val) / (max_val - min_val)
        else:
            peak_y_norm = peak_y

        self.selected_points.append((peak_x, peak_y))

        # Mark on plot
        self.ax.plot(peak_x, peak_y_norm, 'ro', markersize=8)
        self.ax.annotate(
            f"{len(self.selected_points)}",
            (peak_x, peak_y_norm),
            textcoords="offset points",
            xytext=(0, 10),
            ha='center',
            fontsize=9,
            color='red'
        )
        self.draw()

        self.peak_selected.emit(peak_x, peak_y)


class LibrarySelectionWidget(QWidget):
    """
    Widget for selecting reference library values.

    Displays checkboxes for each library value with index and wavenumber.
    """

    selection_changed = pyqtSignal(list)  # Emits list of selected indices

    def __init__(self, library_name: str, parent=None):
        super().__init__(parent)
        self.library_name = library_name
        self.checkboxes = []

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Header with select all/none buttons
        header = QHBoxLayout()
        btn_all = QPushButton("Select All")
        btn_all.clicked.connect(self._select_all)
        btn_none = QPushButton("Clear All")
        btn_none.clicked.connect(self._select_none)
        header.addWidget(btn_all)
        header.addWidget(btn_none)
        header.addStretch()
        layout.addLayout(header)

        # Scrollable area for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_layout = QGridLayout(content)
        content_layout.setSpacing(4)

        # Get library values
        library = ReferenceLibrary.get_library_with_indices(self.library_name)

        # Create checkboxes in grid (3 columns)
        cols = 3
        for i, (idx, value) in enumerate(library):
            cb = QCheckBox(f"[{idx}] {value:.2f}")
            cb.setProperty("lib_index", idx)
            cb.stateChanged.connect(self._on_selection_changed)
            self.checkboxes.append(cb)

            row = i // cols
            col = i % cols
            content_layout.addWidget(cb, row, col)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Selection count label
        self.lbl_count = QLabel("Selected: 0")
        self.lbl_count.setStyleSheet("color: #888;")
        layout.addWidget(self.lbl_count)

    def _select_all(self):
        for cb in self.checkboxes:
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self._on_selection_changed()

    def _select_none(self):
        for cb in self.checkboxes:
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._on_selection_changed()

    def _on_selection_changed(self):
        selected = self.get_selected_indices()
        self.lbl_count.setText(f"Selected: {len(selected)}")
        self.selection_changed.emit(selected)

    def get_selected_indices(self) -> list:
        """Get list of selected library indices."""
        return [
            cb.property("lib_index")
            for cb in self.checkboxes
            if cb.isChecked()
        ]

    def set_selected_indices(self, indices: list):
        """Set which indices are selected."""
        for cb in self.checkboxes:
            cb.blockSignals(True)
            cb.setChecked(cb.property("lib_index") in indices)
            cb.blockSignals(False)
        self._on_selection_changed()


class CalibrationUI(QDialog):
    """
    Main Calibration UI Dialog.

    Correct Workflow:
    1. Select Neon-Argon library values to use
    2. Upload Neon spectrum and select peaks
    3. Choose: known wavelength or use Acetaminophen
       - If KNOWN: Enter wavelength -> Skip to Step 5 (NO Acetaminophen)
       - If UNKNOWN: Go to Step 4 (Acetaminophen)
    4. (Only if unknown) Select Acet library, upload spectrum, select peaks
    5. Run calibration and save result
    """

    calibration_completed = pyqtSignal(dict)  # Emits calibration result

    # Step constants
    STEP_NEON_LIBRARY = 0
    STEP_NEON_SPECTRUM = 1
    STEP_WAVELENGTH_CHOICE = 2
    STEP_ACETAMINOPHEN = 3
    STEP_CALIBRATE = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("X-Axis Calibration")
        self.setMinimumSize(1100, 750)
        self.resize(1200, 800)

        # Calibration processor
        self.processor = CalibrationProcessor()

        # State
        self.current_step = self.STEP_NEON_LIBRARY
        self.wavelength_known = None  # None = not chosen, True = known, False = use acet
        self.neon_file = None
        self.acet_file = None

        # Store neon peaks separately (before moving to wavelength step)
        self.stored_neon_peaks = []

        self._build_ui()
        self._update_step()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("X-Axis Wavenumber Calibration")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - controls
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # Step indicator
        self.lbl_step = QLabel("Step 1: Select Neon-Argon Reference Peaks")
        self.lbl_step.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_step.setStyleSheet("color: #4C8BF5;")
        left_layout.addWidget(self.lbl_step)

        # Instructions
        self.lbl_instructions = QLabel("")
        self.lbl_instructions.setWordWrap(True)
        self.lbl_instructions.setStyleSheet("color: #888; margin-bottom: 10px;")
        left_layout.addWidget(self.lbl_instructions)

        # Stacked widget for different steps (instead of tabs)
        self.stack = QStackedWidget()

        # Page 0: Neon Library Selection
        self.neon_lib_widget = LibrarySelectionWidget("neon")
        self.neon_lib_widget.selection_changed.connect(self._on_neon_selection_changed)
        self.stack.addWidget(self.neon_lib_widget)

        # Page 1: Neon Spectrum & Peak Selection
        neon_spectrum_widget = QWidget()
        neon_spectrum_layout = QVBoxLayout(neon_spectrum_widget)

        btn_upload_neon = QPushButton("Upload Neon-Argon Spectrum")
        btn_upload_neon.clicked.connect(self._upload_neon_spectrum)
        neon_spectrum_layout.addWidget(btn_upload_neon)

        self.lbl_neon_file = QLabel("No file loaded")
        self.lbl_neon_file.setStyleSheet("color: #888;")
        neon_spectrum_layout.addWidget(self.lbl_neon_file)

        self.lbl_neon_peaks = QLabel("Select 0 peaks on the spectrum")
        neon_spectrum_layout.addWidget(self.lbl_neon_peaks)

        btn_clear_neon = QPushButton("Clear Selected Peaks")
        btn_clear_neon.clicked.connect(self._clear_neon_peaks)
        neon_spectrum_layout.addWidget(btn_clear_neon)

        neon_spectrum_layout.addStretch()
        self.stack.addWidget(neon_spectrum_widget)

        # Page 2: Wavelength Choice
        wavelength_widget = QWidget()
        wavelength_layout = QVBoxLayout(wavelength_widget)

        lbl_wl_question = QLabel(
            "Do you know the exact laser excitation wavelength?\n\n"
            "If YES: Enter the wavelength (at least 3 decimal places)\n"
            "        -> You will skip Acetaminophen step and go directly to calibration\n\n"
            "If NO: You will need to upload an Acetaminophen spectrum\n"
            "       -> This method is less accurate"
        )
        lbl_wl_question.setWordWrap(True)
        wavelength_layout.addWidget(lbl_wl_question)

        # Known wavelength option
        known_group = QGroupBox("Option A: Known Wavelength (Recommended)")
        known_layout = QHBoxLayout(known_group)
        known_layout.addWidget(QLabel("Wavelength (nm):"))
        self.input_wavelength = QDoubleSpinBox()
        self.input_wavelength.setRange(400, 1200)
        self.input_wavelength.setDecimals(3)
        self.input_wavelength.setValue(785.000)
        known_layout.addWidget(self.input_wavelength)
        self.btn_use_known = QPushButton("Use This Wavelength")
        self.btn_use_known.setStyleSheet("background: #28a745; color: white; font-weight: bold;")
        self.btn_use_known.clicked.connect(self._use_known_wavelength)
        known_layout.addWidget(self.btn_use_known)
        wavelength_layout.addWidget(known_group)

        # Unknown wavelength option
        unknown_group = QGroupBox("Option B: Estimate from Acetaminophen")
        unknown_layout = QVBoxLayout(unknown_group)
        self.btn_use_acet = QPushButton("Use Acetaminophen Spectrum")
        self.btn_use_acet.clicked.connect(self._use_acetaminophen)
        unknown_layout.addWidget(self.btn_use_acet)
        lbl_warning = QLabel(
            "Warning: This method is less accurate than using a known wavelength.\n"
            "Please make sure you understand the implications before proceeding."
        )
        lbl_warning.setStyleSheet("color: #ff9800;")
        lbl_warning.setWordWrap(True)
        unknown_layout.addWidget(lbl_warning)
        wavelength_layout.addWidget(unknown_group)

        wavelength_layout.addStretch()
        self.stack.addWidget(wavelength_widget)

        # Page 3: Acetaminophen (only if needed)
        acet_widget = QWidget()
        acet_layout = QVBoxLayout(acet_widget)

        # Acetaminophen library selection
        acet_layout.addWidget(QLabel("Select Acetaminophen Reference Peaks:"))
        self.acet_lib_widget = LibrarySelectionWidget("acetaminophen")
        self.acet_lib_widget.selection_changed.connect(self._on_acet_selection_changed)
        acet_layout.addWidget(self.acet_lib_widget)

        btn_upload_acet = QPushButton("Upload Acetaminophen Spectrum")
        btn_upload_acet.clicked.connect(self._upload_acet_spectrum)
        acet_layout.addWidget(btn_upload_acet)

        self.lbl_acet_file = QLabel("No file loaded")
        self.lbl_acet_file.setStyleSheet("color: #888;")
        acet_layout.addWidget(self.lbl_acet_file)

        self.lbl_acet_peaks = QLabel("Select 0 peaks on the spectrum")
        acet_layout.addWidget(self.lbl_acet_peaks)

        btn_clear_acet = QPushButton("Clear Selected Peaks")
        btn_clear_acet.clicked.connect(self._clear_acet_peaks)
        acet_layout.addWidget(btn_clear_acet)

        self.stack.addWidget(acet_widget)

        # Page 4: Calibrate & Save
        calibrate_widget = QWidget()
        calibrate_layout = QVBoxLayout(calibrate_widget)

        self.lbl_summary = QLabel("Calibration Summary")
        self.lbl_summary.setWordWrap(True)
        calibrate_layout.addWidget(self.lbl_summary)

        self.btn_calibrate = QPushButton("Run Calibration")
        self.btn_calibrate.setStyleSheet(
            "background: #4C8BF5; color: white; font-weight: bold; padding: 10px;"
        )
        self.btn_calibrate.clicked.connect(self._run_calibration)
        calibrate_layout.addWidget(self.btn_calibrate)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        calibrate_layout.addWidget(self.progress)

        self.lbl_result = QLabel("")
        self.lbl_result.setWordWrap(True)
        calibrate_layout.addWidget(self.lbl_result)

        self.btn_save = QPushButton("Save Calibration (.mat)")
        self.btn_save.setStyleSheet(
            "background: #28a745; color: white; font-weight: bold; padding: 10px;"
        )
        self.btn_save.clicked.connect(self._save_calibration)
        self.btn_save.setEnabled(False)
        calibrate_layout.addWidget(self.btn_save)

        calibrate_layout.addStretch()
        self.stack.addWidget(calibrate_widget)

        left_layout.addWidget(self.stack)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("< Previous")
        self.btn_prev.clicked.connect(self._prev_step)
        nav_layout.addWidget(self.btn_prev)

        nav_layout.addStretch()

        self.btn_next = QPushButton("Next >")
        self.btn_next.clicked.connect(self._next_step)
        nav_layout.addWidget(self.btn_next)

        left_layout.addLayout(nav_layout)

        # Right panel - spectrum display
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        self.canvas = SpectrumCanvas(self, width=8, height=5)
        self.canvas.peak_selected.connect(self._on_peak_selected)
        self.toolbar = NavigationToolbar(self.canvas, self)

        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)

        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 700])

        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Select Neon-Argon reference peaks to begin")
        main_layout.addWidget(self.status_bar)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_cancel)

        self.btn_finish = QPushButton("Finish")
        self.btn_finish.setStyleSheet("background: #4C8BF5; color: white;")
        self.btn_finish.clicked.connect(self.accept)
        self.btn_finish.setEnabled(False)
        bottom_layout.addWidget(self.btn_finish)

        main_layout.addLayout(bottom_layout)

    def _update_step(self):
        """Update UI based on current step."""
        self.stack.setCurrentIndex(self.current_step)

        steps_info = {
            self.STEP_NEON_LIBRARY: (
                "Step 1: Select Neon-Argon Reference Peaks",
                "Check the wavenumber values you want to use for calibration. "
                "These will be matched to peaks you select on the spectrum."
            ),
            self.STEP_NEON_SPECTRUM: (
                "Step 2: Upload and Select Neon Peaks",
                "Upload your Neon-Argon spectrum and click on the peaks that "
                "correspond to your selected reference values (in order)."
            ),
            self.STEP_WAVELENGTH_CHOICE: (
                "Step 3: Specify Laser Wavelength",
                "Choose whether to enter a known wavelength (recommended) or "
                "estimate it using an Acetaminophen spectrum."
            ),
            self.STEP_ACETAMINOPHEN: (
                "Step 4: Acetaminophen Calibration",
                "Select reference peaks and click on matching peaks in your "
                "Acetaminophen spectrum to estimate the laser wavelength."
            ),
            self.STEP_CALIBRATE: (
                "Step 5: Run Calibration",
                "Review your selections and run the calibration. Save the "
                "result as a .mat file."
            ),
        }

        if self.current_step in steps_info:
            self.lbl_step.setText(steps_info[self.current_step][0])
            self.lbl_instructions.setText(steps_info[self.current_step][1])

        # Update navigation buttons
        self.btn_prev.setEnabled(self.current_step > 0)

        # Hide Next button on wavelength choice step (user must click specific button)
        # Also hide on calibrate step
        if self.current_step == self.STEP_WAVELENGTH_CHOICE:
            self.btn_next.setVisible(False)
        elif self.current_step == self.STEP_CALIBRATE:
            self.btn_next.setVisible(False)
        else:
            self.btn_next.setVisible(True)
            self.btn_next.setEnabled(True)

        # Update canvas selection mode
        if self.current_step == self.STEP_NEON_SPECTRUM:
            # Neon spectrum mode
            self.canvas.enable_selection(True)
            neon_count = len(self.neon_lib_widget.get_selected_indices())
            self.canvas.set_max_points(neon_count)
        elif self.current_step == self.STEP_ACETAMINOPHEN:
            # Acetaminophen spectrum mode
            self.canvas.enable_selection(True)
            acet_count = len(self.acet_lib_widget.get_selected_indices())
            self.canvas.set_max_points(acet_count)
        else:
            self.canvas.enable_selection(False)

        # Update summary when on calibrate step
        if self.current_step == self.STEP_CALIBRATE:
            self._update_summary()

    def _prev_step(self):
        """Go to previous step with proper handling."""
        if self.current_step == self.STEP_CALIBRATE:
            # Going back from calibration
            if self.wavelength_known:
                # If wavelength was known, go back to wavelength choice
                self.current_step = self.STEP_WAVELENGTH_CHOICE
            else:
                # If using acetaminophen, go back to acetaminophen step
                self.current_step = self.STEP_ACETAMINOPHEN
        elif self.current_step == self.STEP_ACETAMINOPHEN:
            # Going back from acetaminophen goes to wavelength choice
            self.current_step = self.STEP_WAVELENGTH_CHOICE
        elif self.current_step > 0:
            self.current_step -= 1

        self._update_step()

    def _next_step(self):
        """Go to next step with validation."""
        if self.current_step == self.STEP_NEON_LIBRARY:
            # Validate neon library selection
            if len(self.neon_lib_widget.get_selected_indices()) == 0:
                QMessageBox.warning(self, "Selection Required",
                                   "Please select at least one reference peak.")
                return
            self.current_step = self.STEP_NEON_SPECTRUM

        elif self.current_step == self.STEP_NEON_SPECTRUM:
            # Validate neon spectrum and peaks
            if self.processor.neon_spectrum is None:
                QMessageBox.warning(self, "Spectrum Required",
                                   "Please upload a Neon-Argon spectrum.")
                return
            expected = len(self.neon_lib_widget.get_selected_indices())
            selected = len(self.canvas.get_selected_points())
            if selected != expected:
                QMessageBox.warning(self, "Peak Selection",
                                   f"Please select exactly {expected} peaks "
                                   f"(currently {selected} selected).")
                return

            # IMPORTANT: Store the neon peaks BEFORE moving to next step
            self.stored_neon_peaks = self.canvas.get_selected_points()
            self.processor.set_neon_selected_peaks(self.stored_neon_peaks)

            self.current_step = self.STEP_WAVELENGTH_CHOICE

        elif self.current_step == self.STEP_ACETAMINOPHEN:
            # Validate acetaminophen spectrum and peaks
            if self.processor.acet_spectrum is None:
                QMessageBox.warning(self, "Spectrum Required",
                                   "Please upload an Acetaminophen spectrum.")
                return
            expected = len(self.acet_lib_widget.get_selected_indices())
            selected = len(self.canvas.get_selected_points())
            if selected != expected:
                QMessageBox.warning(self, "Peak Selection",
                                   f"Please select exactly {expected} peaks "
                                   f"(currently {selected} selected).")
                return

            # Store acetaminophen peaks
            self.processor.set_acet_selected_peaks(self.canvas.get_selected_points())

            self.current_step = self.STEP_CALIBRATE

        self._update_step()

    def _on_neon_selection_changed(self, indices):
        """Handle Neon library selection change."""
        self.processor.set_neon_library_selection(indices)
        count = len(indices)
        self.lbl_neon_peaks.setText(f"Select {count} peaks on the spectrum")
        self.canvas.set_max_points(count)
        self.status_bar.showMessage(f"Neon library: {count} peaks selected")

    def _on_acet_selection_changed(self, indices):
        """Handle Acetaminophen library selection change."""
        self.processor.set_acet_library_selection(indices)
        count = len(indices)
        self.lbl_acet_peaks.setText(f"Select {count} peaks on the spectrum")
        self.canvas.set_max_points(count)

    def _upload_neon_spectrum(self):
        """Upload Neon-Argon spectrum file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Neon-Argon Spectrum",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not filepath:
            return

        try:
            spectrum = load_spectrum_file(filepath)
            self.processor.set_neon_spectrum(spectrum)
            self.neon_file = filepath

            # Display on canvas
            self.canvas.load_spectrum(spectrum, "Neon-Argon Spectrum")
            self.canvas.enable_selection(True)
            self.canvas.set_max_points(len(self.neon_lib_widget.get_selected_indices()))

            self.lbl_neon_file.setText(f"Loaded: {os.path.basename(filepath)}")
            self.lbl_neon_file.setStyleSheet("color: #28a745;")
            self.status_bar.showMessage(f"Neon spectrum loaded: {len(spectrum)} points")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load spectrum:\n{e}")

    def _upload_acet_spectrum(self):
        """Upload Acetaminophen spectrum file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Acetaminophen Spectrum",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not filepath:
            return

        try:
            spectrum = load_spectrum_file(filepath)
            self.processor.set_acet_spectrum(spectrum)
            self.acet_file = filepath

            # Display on canvas
            self.canvas.load_spectrum(spectrum, "Acetaminophen Spectrum")
            self.canvas.enable_selection(True)
            self.canvas.set_max_points(len(self.acet_lib_widget.get_selected_indices()))

            self.lbl_acet_file.setText(f"Loaded: {os.path.basename(filepath)}")
            self.lbl_acet_file.setStyleSheet("color: #28a745;")
            self.status_bar.showMessage(f"Acetaminophen spectrum loaded")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load spectrum:\n{e}")

    def _clear_neon_peaks(self):
        """Clear Neon peak selection."""
        self.canvas.clear_selection()
        self.status_bar.showMessage("Neon peak selection cleared")

    def _clear_acet_peaks(self):
        """Clear Acetaminophen peak selection."""
        self.canvas.clear_selection()
        self.status_bar.showMessage("Acetaminophen peak selection cleared")

    def _on_peak_selected(self, pixel, intensity):
        """Handle peak selection on canvas."""
        count = len(self.canvas.get_selected_points())
        if self.current_step == self.STEP_NEON_SPECTRUM:
            expected = len(self.neon_lib_widget.get_selected_indices())
            self.status_bar.showMessage(f"Neon peaks: {count}/{expected} selected")
        elif self.current_step == self.STEP_ACETAMINOPHEN:
            expected = len(self.acet_lib_widget.get_selected_indices())
            self.status_bar.showMessage(f"Acetaminophen peaks: {count}/{expected} selected")

    def _use_known_wavelength(self):
        """
        Use the entered known wavelength.
        SKIPS Acetaminophen step entirely and goes directly to calibration.
        """
        wavelength = self.input_wavelength.value()
        self.processor.set_known_wavelength(wavelength)
        self.wavelength_known = True

        # IMPORTANT: Skip acetaminophen step entirely, go directly to calibration
        self.current_step = self.STEP_CALIBRATE
        self._update_step()

        self.status_bar.showMessage(f"Using known wavelength: {wavelength:.3f} nm - Skipping Acetaminophen")

    def _use_acetaminophen(self):
        """
        Use Acetaminophen spectrum to estimate wavelength.
        Goes to Acetaminophen step.
        """
        self.wavelength_known = False

        # Go to Acetaminophen step
        self.current_step = self.STEP_ACETAMINOPHEN
        self._update_step()

        self.status_bar.showMessage("Select Acetaminophen library peaks and upload spectrum")

    def _update_summary(self):
        """Update calibration summary display."""
        neon_indices = self.neon_lib_widget.get_selected_indices()

        summary = f"Calibration Configuration:\n\n"
        summary += f"Neon-Argon: {len(neon_indices)} reference peaks selected\n"
        summary += f"Neon peaks (pixels): {self.stored_neon_peaks}\n\n"

        if self.wavelength_known:
            summary += f"Method: Known Wavelength\n"
            summary += f"Wavelength: {self.processor.laser_wavelength:.3f} nm\n\n"
            summary += "Acetaminophen: NOT USED (wavelength is known)\n"
        else:
            acet_indices = self.acet_lib_widget.get_selected_indices()
            summary += f"Method: Estimate from Acetaminophen\n"
            summary += f"Acetaminophen: {len(acet_indices)} reference peaks selected\n\n"
            summary += "Wavelength: Will be estimated during calibration\n"

        self.lbl_summary.setText(summary)

    def _run_calibration(self):
        """Run the calibration process."""
        try:
            self.progress.setVisible(True)
            self.progress.setValue(10)
            QApplication.processEvents()

            self.progress.setValue(30)
            QApplication.processEvents()

            # Run calibration based on method
            if self.wavelength_known:
                # Known wavelength - NO acetaminophen data used
                wvn = self.processor.calibrate_with_known_wavelength()
            else:
                # Unknown wavelength - use acetaminophen
                wvn = self.processor.calibrate_with_acetaminophen()

            self.progress.setValue(80)
            QApplication.processEvents()

            # Get error statistics
            errors = self.processor.get_calibration_error()

            self.progress.setValue(100)

            # Display result
            result_text = f"Calibration completed successfully!\n\n"
            result_text += f"Wavenumber range: {wvn.min():.1f} to {wvn.max():.1f} cm^-1\n"
            result_text += f"Spectrum length: {len(wvn)} points\n"

            if self.processor.laser_wavelength:
                result_text += f"Laser wavelength: {self.processor.laser_wavelength:.3f} nm\n"

            if 'neon_mean_abs_error' in errors:
                result_text += f"\nMean absolute error: {errors['neon_mean_abs_error']:.4f} cm^-1\n"
                result_text += f"Max error: {errors['neon_max_error']:.4f} cm^-1\n"

            self.lbl_result.setText(result_text)
            self.lbl_result.setStyleSheet("color: #28a745;")

            self.btn_save.setEnabled(True)
            self.btn_finish.setEnabled(True)

            self.status_bar.showMessage("Calibration completed successfully")

            # Plot result on canvas
            self.canvas.ax.clear()
            self.canvas.ax.plot(wvn, 'b-', linewidth=0.8)
            self.canvas.ax.set_title("Calibrated Wavenumber Axis")
            self.canvas.ax.set_xlabel("Pixel")
            self.canvas.ax.set_ylabel("Wavenumber (cm^-1)")
            self.canvas.ax.grid(True, alpha=0.3)
            self.canvas.draw()

        except Exception as e:
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Calibration Error", f"Calibration failed:\n{e}")
            self.status_bar.showMessage("Calibration failed")

    def _save_calibration(self):
        """Save calibration result to .mat file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration",
            "calibration.mat",
            "MAT Files (*.mat);;All Files (*)"
        )
        if not filepath:
            return

        if not filepath.endswith('.mat'):
            filepath += '.mat'

        try:
            result = self.processor.get_calibration_result()
            savemat(filepath, {'Cal': result})

            QMessageBox.information(
                self, "Saved",
                f"Calibration saved to:\n{filepath}"
            )
            self.status_bar.showMessage(f"Calibration saved: {filepath}")

            self.calibration_completed.emit(result)

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save:\n{e}")


# Quick test
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Apply dark theme
    app.setStyleSheet("""
        QWidget {
            font-family: 'Segoe UI';
            color: #EAEAEA;
            background: #121212;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #333;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }
        QPushButton {
            background: #1F1F1F;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
        }
        QPushButton:hover { background: #2A2A2A; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #1F1F1F;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 6px;
        }
        QCheckBox {
            spacing: 6px;
        }
        QScrollArea {
            border: none;
        }
    """)

    dlg = CalibrationUI()
    dlg.exec_()
    sys.exit(app.exec_())
