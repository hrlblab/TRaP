#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P_Mean Process UI - Enhanced Version

Features:
- Dual plot layout (current spectrum + before/after comparison)
- Step progress indicator with visual feedback
- Organized parameter panels with GroupBox
- Processing history visualization
- Improved navigation with skip options
"""

import json
import sys
import os
from datetime import datetime

from utils.io import rdata, wdata
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QLineEdit, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox,
    QComboBox, QListWidget, QGroupBox, QFormLayout, QSplitter,
    QProgressBar, QFrame, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from scipy.signal import medfilt

from UI_utils.UI_Config_Manager import ConfigManager
from utils.SpectralPreprocess import (
    Binning, Denoise, Truncate, CosmicRayRemoval,
    SpectralResponseCorrection, subtractBaseline,
    FluorescenceBackgroundSubtraction, Normalize
)

config_manager = ConfigManager()


def moving_average(data, window=5):
    return np.convolve(data, np.ones(window) / window, mode='same')


def median_filter(data, kernel_size=5):
    if kernel_size % 2 == 0:
        kernel_size += 1
    return medfilt(data, kernel_size=kernel_size)


class DualPlotCanvas(FigureCanvas):
    """Canvas with two subplots for current view and comparison."""

    def __init__(self, parent=None, width=10, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor('#f8f9fa')

        # Create subplots
        self.ax_current = self.fig.add_subplot(211)
        self.ax_compare = self.fig.add_subplot(212)

        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._style_axes()

    def _style_axes(self):
        """Apply consistent styling to axes."""
        for ax in [self.ax_current, self.ax_compare]:
            ax.set_facecolor('#ffffff')
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.tick_params(labelsize=9)

        self.ax_current.set_title("Current Spectrum", fontsize=11, fontweight='bold')
        self.ax_compare.set_title("Processing Comparison", fontsize=11, fontweight='bold')
        self.fig.tight_layout(pad=2.0)

    def plot_current(self, wvn, spect, title=None):
        """Plot the current spectrum state."""
        self.ax_current.clear()
        if wvn is not None and len(wvn) == len(spect):
            self.ax_current.plot(wvn, spect, 'b-', linewidth=1.2, label='Current')
            self.ax_current.set_xlabel("Wavenumber (cm$^{-1}$)", fontsize=10)
        else:
            self.ax_current.plot(spect, 'b-', linewidth=1.2, label='Current')
            self.ax_current.set_xlabel("Index", fontsize=10)

        self.ax_current.set_ylabel("Intensity", fontsize=10)
        self.ax_current.set_title(title or "Current Spectrum", fontsize=11, fontweight='bold')
        self.ax_current.grid(True, alpha=0.3, linestyle='--')
        self.ax_current.legend(loc='best', fontsize=9)
        self.fig.tight_layout(pad=2.0)
        self.draw()

    def plot_comparison(self, wvn, before, after, before_label="Before", after_label="After"):
        """Plot before/after comparison."""
        self.ax_compare.clear()

        if wvn is not None and len(wvn) == len(before):
            self.ax_compare.plot(wvn, before, 'b-', linewidth=1, alpha=0.6, label=before_label)
            if after is not None and len(after) == len(wvn):
                self.ax_compare.plot(wvn, after, 'r-', linewidth=1.2, label=after_label)
            self.ax_compare.set_xlabel("Wavenumber (cm$^{-1}$)", fontsize=10)
        else:
            self.ax_compare.plot(before, 'b-', linewidth=1, alpha=0.6, label=before_label)
            if after is not None:
                self.ax_compare.plot(after, 'r-', linewidth=1.2, label=after_label)
            self.ax_compare.set_xlabel("Index", fontsize=10)

        self.ax_compare.set_ylabel("Intensity", fontsize=10)
        self.ax_compare.set_title("Processing Comparison", fontsize=11, fontweight='bold')
        self.ax_compare.grid(True, alpha=0.3, linestyle='--')
        self.ax_compare.legend(loc='best', fontsize=9)
        self.fig.tight_layout(pad=2.0)
        self.draw()

    def plot_polyfit(self, wvn, spect, baseline):
        """Plot spectrum with polyfit baseline."""
        self.ax_compare.clear()

        if wvn is not None and len(wvn) == len(spect):
            self.ax_compare.plot(wvn, spect, 'b-', linewidth=1.2, label='Spectrum')
            self.ax_compare.plot(wvn, baseline, 'r--', linewidth=1.5, label='Polyfit Baseline')
            self.ax_compare.set_xlabel("Wavenumber (cm$^{-1}$)", fontsize=10)
        else:
            self.ax_compare.plot(spect, 'b-', linewidth=1.2, label='Spectrum')
            self.ax_compare.plot(baseline, 'r--', linewidth=1.5, label='Polyfit Baseline')
            self.ax_compare.set_xlabel("Index", fontsize=10)

        self.ax_compare.set_ylabel("Intensity", fontsize=10)
        self.ax_compare.set_title("Polyfit Baseline Preview", fontsize=11, fontweight='bold')
        self.ax_compare.grid(True, alpha=0.3, linestyle='--')
        self.ax_compare.legend(loc='best', fontsize=9)
        self.ax_compare.fill_between(
            wvn if wvn is not None and len(wvn) == len(spect) else range(len(spect)),
            baseline, spect, alpha=0.15, color='green', label='Background'
        )
        self.fig.tight_layout(pad=2.0)
        self.draw()


class StepIndicator(QWidget):
    """Visual step progress indicator."""

    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self.steps = steps
        self.current_index = 0
        self.step_labels = []
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        for i, step in enumerate(self.steps):
            # Step indicator
            frame = QFrame()
            frame.setFixedHeight(30)
            frame_layout = QHBoxLayout(frame)
            frame_layout.setContentsMargins(5, 2, 5, 2)

            label = QLabel(f"{i}. {step[:12]}..." if len(step) > 15 else f"{i}. {step}")
            label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont("Arial", 8))
            label.setToolTip(step)
            frame_layout.addWidget(label)

            self.step_labels.append((frame, label))
            layout.addWidget(frame)

        self._update_styles()

    def _update_styles(self):
        for i, (frame, label) in enumerate(self.step_labels):
            if i < self.current_index:
                # Completed
                frame.setStyleSheet("background-color: #28a745; border-radius: 3px;")
                label.setStyleSheet("color: white; font-weight: bold;")
            elif i == self.current_index:
                # Current
                frame.setStyleSheet("background-color: #007bff; border-radius: 3px;")
                label.setStyleSheet("color: white; font-weight: bold;")
            else:
                # Pending
                frame.setStyleSheet("background-color: #e9ecef; border-radius: 3px;")
                label.setStyleSheet("color: #6c757d;")

    def set_step(self, index):
        self.current_index = min(max(0, index), len(self.steps))
        self._update_styles()


class P_Mean_Process_UI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_system = config_manager.params.get("System", "")

        self.setWindowTitle("Spectrum Data Process - Enhanced")
        self.setGeometry(50, 50, 1400, 900)
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f6f8; }
            QGroupBox {
                font-weight: 600;
                font-size: 13px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 14px;
                padding: 12px 8px 8px 8px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #1a73e8;
            }
            QPushButton {
                padding: 10px 18px;
                border-radius: 6px;
                border: 2px solid #dadce0;
                background-color: #ffffff;
                color: #3c4043;
                font-size: 13px;
                font-weight: 500;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #f1f3f4;
                border-color: #c6c9cc;
            }
            QPushButton:pressed {
                background-color: #e8eaed;
            }
            QPushButton:disabled {
                background-color: #f1f3f4;
                color: #9aa0a6;
                border-color: #e8eaed;
            }
            QPushButton[class="primary"] {
                background-color: #1a73e8;
                color: white;
                border: none;
                font-weight: 600;
            }
            QPushButton[class="primary"]:hover {
                background-color: #1557b0;
            }
            QPushButton[class="primary"]:pressed {
                background-color: #174ea6;
            }
            QPushButton[class="success"] {
                background-color: #1e8e3e;
                color: white;
                border: none;
                font-weight: 600;
            }
            QPushButton[class="success"]:hover {
                background-color: #137333;
            }
            QPushButton[class="danger"] {
                background-color: #d93025;
                color: white;
                border: none;
            }
            QPushButton[class="danger"]:hover {
                background-color: #b31412;
            }
            QLineEdit {
                padding: 8px 10px;
                border: 2px solid #dadce0;
                border-radius: 6px;
                background-color: #ffffff;
                font-size: 13px;
                color: #202124;
            }
            QLineEdit:focus {
                border-color: #1a73e8;
                background-color: #ffffff;
            }
            QComboBox {
                padding: 8px 10px;
                border: 2px solid #dadce0;
                border-radius: 6px;
                background-color: #ffffff;
                font-size: 13px;
                color: #202124;
                min-height: 20px;
            }
            QComboBox:focus {
                border-color: #1a73e8;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QListWidget {
                border: 2px solid #dadce0;
                border-radius: 6px;
                background-color: #ffffff;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px 0;
            }
            QListWidget::item:hover {
                background-color: #f1f3f4;
            }
            QListWidget::item:selected {
                background-color: #e8f0fe;
                color: #1a73e8;
            }
            QLabel {
                color: #3c4043;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

        # Data state
        self.wvnFull = np.zeros([100, 1])
        self.rawSpect = np.zeros(self.wvnFull.shape)
        self.current_spect = self.rawSpect.copy()
        self.current_wvn = self.wvnFull.copy()
        self.previous_spect = None  # For comparison
        self.previous_wvn = None
        self.wlCorr = np.ones((500, 1)) * 1.2

        self.operations = []
        self.history = []
        self.processing_steps = [
            "Load Data",
            "SubtractBaseline",
            "SpectralResponseCorrection",
            "CosmicRayRemoval",
            "Truncate",
            "Binning",
            "Denoise",
            "Polyfit Preview",
            "FluorescenceBackgroundSubtraction",
            "Normalization"
        ]
        self.current_step_index = 0

        self._build_ui()
        self._update_ui_state()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(10)

        # Left panel - Controls
        left_panel = QWidget()
        left_panel.setFixedWidth(380)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        # Step indicator (scrollable)
        step_scroll = QScrollArea()
        step_scroll.setWidgetResizable(True)
        step_scroll.setFixedHeight(50)
        step_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.step_indicator = StepIndicator(self.processing_steps)
        step_scroll.setWidget(self.step_indicator)
        left_layout.addWidget(step_scroll)

        # Current step info
        self.lbl_step_info = QLabel("Step 0: Load Data")
        self.lbl_step_info.setStyleSheet("font-size: 14px; font-weight: bold; color: #007bff; padding: 5px;")
        left_layout.addWidget(self.lbl_step_info)

        # Parameters Group
        params_group = QGroupBox("Processing Parameters")
        params_layout = QFormLayout(params_group)

        self.edit_start = QLineEdit("900")
        self.edit_stop = QLineEdit("1700")
        self.edit_polyorder = QLineEdit("7")
        self.edit_binwidth = QLineEdit("3.5")

        params_layout.addRow("Truncate Start (cm⁻¹):", self.edit_start)
        params_layout.addRow("Truncate Stop (cm⁻¹):", self.edit_stop)
        params_layout.addRow("Polyorder:", self.edit_polyorder)
        params_layout.addRow("Bin Width:", self.edit_binwidth)

        left_layout.addWidget(params_group)

        # Denoise Group
        denoise_group = QGroupBox("Denoise Settings")
        denoise_layout = QFormLayout(denoise_group)

        self.combo_denoise = QComboBox()
        self.combo_denoise.addItems(["Savitzky-Golay", "Moving Average", "Median Filter", "None"])
        self.combo_denoise.currentTextChanged.connect(self._update_denoise_visibility)
        denoise_layout.addRow("Method:", self.combo_denoise)

        self.edit_sgorder = QLineEdit("2")
        self.edit_sgframe = QLineEdit("7")
        self.edit_mawindow = QLineEdit("5")
        self.edit_mediank = QLineEdit("5")

        self.lbl_sgorder = QLabel("SG Order:")
        self.lbl_sgframe = QLabel("SG Frame:")
        self.lbl_mawindow = QLabel("MA Window:")
        self.lbl_mediank = QLabel("Median Kernel:")

        denoise_layout.addRow(self.lbl_sgorder, self.edit_sgorder)
        denoise_layout.addRow(self.lbl_sgframe, self.edit_sgframe)
        denoise_layout.addRow(self.lbl_mawindow, self.edit_mawindow)
        denoise_layout.addRow(self.lbl_mediank, self.edit_mediank)

        left_layout.addWidget(denoise_group)
        self._update_denoise_visibility()

        # Config Group
        config_group = QGroupBox("Configuration")
        config_layout = QHBoxLayout(config_group)
        btn_save_config = QPushButton("Save Config")
        btn_save_config.clicked.connect(self.on_save_config)
        btn_load_config = QPushButton("Load Config")
        btn_load_config.clicked.connect(self.on_load_config)
        config_layout.addWidget(btn_save_config)
        config_layout.addWidget(btn_load_config)
        left_layout.addWidget(config_group)

        # Navigation Group
        nav_group = QGroupBox("Navigation")
        nav_layout = QVBoxLayout(nav_group)

        # Load data button
        self.btn_load = QPushButton("Load Data Files")
        self.btn_load.setProperty("class", "success")
        self.btn_load.clicked.connect(self.on_load_rdata_files)
        nav_layout.addWidget(self.btn_load)

        # Step navigation
        step_nav = QHBoxLayout()
        self.btn_previous = QPushButton("< Previous")
        self.btn_previous.clicked.connect(self.on_previous_step)
        self.btn_next = QPushButton("Next >")
        self.btn_next.clicked.connect(self.on_next_step)
        self.btn_next.setProperty("class", "primary")
        step_nav.addWidget(self.btn_previous)
        step_nav.addWidget(self.btn_next)
        nav_layout.addLayout(step_nav)

        # Save buttons
        save_layout = QHBoxLayout()
        self.btn_save_fig = QPushButton("Save Figure")
        self.btn_save_fig.clicked.connect(self.on_save_figure)
        self.btn_save_data = QPushButton("Save Data")
        self.btn_save_data.clicked.connect(self.on_save_data)
        save_layout.addWidget(self.btn_save_fig)
        save_layout.addWidget(self.btn_save_data)
        nav_layout.addLayout(save_layout)

        left_layout.addWidget(nav_group)

        # History Group
        history_group = QGroupBox("Processing History")
        history_layout = QVBoxLayout(history_group)
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(120)
        history_layout.addWidget(self.history_list)
        left_layout.addWidget(history_group)

        left_layout.addStretch()

        # Right panel - Plots
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Plot canvas
        self.canvas = DualPlotCanvas(self, width=10, height=8, dpi=100)
        self.toolbar = NavigationToolbar(self.canvas, self)
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)

        # Status bar
        self.lbl_status = QLabel("Ready. Load data files to begin processing.")
        self.lbl_status.setStyleSheet("padding: 5px; background-color: #e9ecef; border-radius: 3px;")
        right_layout.addWidget(self.lbl_status)

        # Add to main layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)

    def _update_denoise_visibility(self):
        """Show/hide denoise parameters based on method."""
        method = self.combo_denoise.currentText()

        is_sg = method == "Savitzky-Golay"
        is_ma = method == "Moving Average"
        is_med = method == "Median Filter"

        self.lbl_sgorder.setVisible(is_sg)
        self.edit_sgorder.setVisible(is_sg)
        self.lbl_sgframe.setVisible(is_sg)
        self.edit_sgframe.setVisible(is_sg)
        self.lbl_mawindow.setVisible(is_ma)
        self.edit_mawindow.setVisible(is_ma)
        self.lbl_mediank.setVisible(is_med)
        self.edit_mediank.setVisible(is_med)

    def _update_ui_state(self):
        """Update UI based on current state."""
        has_data = len(self.history) > 0
        self.btn_previous.setEnabled(has_data and self.current_step_index > 1)
        self.btn_next.setEnabled(has_data and self.current_step_index < len(self.processing_steps))
        self.btn_save_fig.setEnabled(has_data)
        self.btn_save_data.setEnabled(has_data)

        self.step_indicator.set_step(self.current_step_index)

        if self.current_step_index < len(self.processing_steps):
            step_name = self.processing_steps[self.current_step_index]
            self.lbl_step_info.setText(f"Step {self.current_step_index}: {step_name}")
        else:
            self.lbl_step_info.setText("Processing Complete!")
            self.lbl_step_info.setStyleSheet("font-size: 14px; font-weight: bold; color: #28a745; padding: 5px;")

    def _update_plots(self, show_comparison=True):
        """Update both plots."""
        # Current spectrum
        self.canvas.plot_current(
            self.current_wvn.flatten() if self.current_wvn is not None else None,
            self.current_spect.flatten() if self.current_spect is not None else np.array([]),
            title=f"Current: Step {self.current_step_index}"
        )

        # Comparison
        if show_comparison and self.previous_spect is not None:
            # Use matching wavenumber for comparison
            if self.previous_wvn is not None and len(self.previous_wvn) == len(self.previous_spect):
                wvn_for_compare = self.previous_wvn.flatten()
            else:
                wvn_for_compare = None

            # If lengths match, show both
            if len(self.previous_spect) == len(self.current_spect):
                self.canvas.plot_comparison(
                    wvn_for_compare,
                    self.previous_spect.flatten(),
                    self.current_spect.flatten(),
                    "Before", "After"
                )
            else:
                self.canvas.plot_comparison(
                    wvn_for_compare,
                    self.previous_spect.flatten(),
                    None,
                    "Previous State", ""
                )

    def add_history(self, op_name):
        """Add processing step to history."""
        state = {
            "op": op_name,
            "wvn": np.copy(self.current_wvn),
            "spect": np.copy(self.current_spect),
            "ops": self.operations.copy(),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        self.history.append(state)
        self.history_list.addItem(f"[{state['timestamp']}] {op_name}")
        self.history_list.scrollToBottom()

    def on_save_config(self):
        """Save configuration to JSON file."""
        config = {}
        try:
            config["Start"] = float(self.edit_start.text())
            config["Stop"] = float(self.edit_stop.text())
            config["Polyorder"] = int(self.edit_polyorder.text())
            config["DenoiseMethod"] = self.combo_denoise.currentText()
            config["BinWidth"] = float(self.edit_binwidth.text())
            config["SGorder"] = int(self.edit_sgorder.text())
            config["SGframe"] = int(self.edit_sgframe.text())
            config["MAWindow"] = int(self.edit_mawindow.text())
            config["MedianKernel"] = int(self.edit_mediank.text())
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Parameter error: {e}")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Config", "p_mean_config.json", "JSON Files (*.json)"
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4)
                self.lbl_status.setText(f"Config saved: {filepath}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save: {e}")

    def on_load_config(self):
        """Load configuration from JSON file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Config", "", "JSON Files (*.json)"
        )
        if filepath:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.edit_start.setText(str(config.get("Start", 900)))
                self.edit_stop.setText(str(config.get("Stop", 1700)))
                self.edit_polyorder.setText(str(config.get("Polyorder", 7)))
                self.combo_denoise.setCurrentText(config.get("DenoiseMethod", "Savitzky-Golay"))
                self.edit_binwidth.setText(str(config.get("BinWidth", 3.5)))
                self.edit_sgorder.setText(str(config.get("SGorder", 2)))
                self.edit_sgframe.setText(str(config.get("SGframe", 7)))
                self.edit_mawindow.setText(str(config.get("MAWindow", 5)))
                self.edit_mediank.setText(str(config.get("MedianKernel", 5)))
                self.lbl_status.setText(f"Config loaded: {filepath}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load: {e}")

    def on_previous_step(self):
        """Go back to previous processing step."""
        if len(self.history) < 2:
            QMessageBox.warning(self, "Error", "No previous state available.")
            return

        self.history.pop()
        self.history_list.takeItem(self.history_list.count() - 1)

        last_state = self.history[-1]
        self.previous_spect = np.copy(self.current_spect)
        self.previous_wvn = np.copy(self.current_wvn)
        self.current_wvn = np.copy(last_state["wvn"])
        self.current_spect = np.copy(last_state["spect"])
        self.operations = last_state["ops"].copy()

        if self.current_step_index > 0:
            self.current_step_index -= 1

        self._update_plots()
        self._update_ui_state()
        self.lbl_status.setText(f"Reverted to: {last_state['op']}")

    def on_next_step(self):
        """Execute next processing step."""
        if self.current_step_index >= len(self.processing_steps):
            QMessageBox.information(self, "Complete", "All processing steps completed!")
            return

        step = self.processing_steps[self.current_step_index]

        # Save previous state for comparison
        self.previous_spect = np.copy(self.current_spect)
        self.previous_wvn = np.copy(self.current_wvn)

        try:
            if step == "Load Data":
                QMessageBox.info(self, "Info", "Please use 'Load Data Files' button.")
                return

            elif step == "SubtractBaseline":
                self.current_spect = subtractBaseline(self.current_spect)
                self.operations.append("SubtractBaseline")

            elif step == "SpectralResponseCorrection":
                self.current_spect = SpectralResponseCorrection(self.wlCorr, self.current_spect)
                self.operations.append("SpectralResponseCorrection")

            elif step == "CosmicRayRemoval":
                self.current_spect = CosmicRayRemoval(self.current_spect)
                self.operations.append("CosmicRayRemoval")

            elif step == "Truncate":
                start = float(self.edit_start.text())
                stop = float(self.edit_stop.text())
                self.current_wvn, self.current_spect = Truncate(
                    start, stop, self.wvnFull, self.current_spect
                )
                self.operations.append(f"Truncate({start}-{stop})")

            elif step == "Binning":
                if self.current_wvn.size == 0:
                    QMessageBox.warning(self, "Warning", "No data to bin!")
                    return
                start = self.current_wvn.flatten()[0]
                stop = self.current_wvn.flatten()[-1]
                binwidth = float(self.edit_binwidth.text())
                if binwidth <= 0:
                    QMessageBox.warning(self, "Error", "BinWidth must be positive!")
                    return
                binned_spect, new_wvn = Binning(
                    start, stop, self.current_wvn.flatten(),
                    self.current_spect.flatten(), binwidth=binwidth
                )
                self.current_spect = binned_spect
                self.current_wvn = new_wvn
                self.operations.append(f"Binning(binwidth={binwidth})")

            elif step == "Denoise":
                method = self.combo_denoise.currentText()
                if method == "Savitzky-Golay":
                    sg_order = int(self.edit_sgorder.text())
                    sg_frame = int(self.edit_sgframe.text())
                    if sg_frame < 3 or sg_frame % 2 == 0:
                        QMessageBox.warning(self, "Error", "SGframe must be odd >= 3!")
                        return
                    self.current_spect = Denoise(self.current_spect, SGorder=sg_order, SGframe=sg_frame)
                    self.operations.append(f"Denoise(SG,o={sg_order},f={sg_frame})")
                elif method == "Moving Average":
                    w = int(self.edit_mawindow.text())
                    self.current_spect = moving_average(self.current_spect.flatten(), window=w)
                    self.operations.append(f"Denoise(MA,w={w})")
                elif method == "Median Filter":
                    k = int(self.edit_mediank.text())
                    self.current_spect = median_filter(self.current_spect.flatten(), kernel_size=k)
                    self.operations.append(f"Denoise(Med,k={k})")
                else:
                    self.operations.append("Denoise(None)")

            elif step == "Polyfit Preview":
                polyorder = int(self.edit_polyorder.text())
                base, _ = FluorescenceBackgroundSubtraction(self.current_spect.flatten(), polyorder)
                # Show polyfit preview without modifying data
                wvn = self.current_wvn.flatten() if self.current_wvn is not None else None
                self.canvas.plot_polyfit(wvn, self.current_spect.flatten(), base)
                self.operations.append(f"PolyfitPreview(order={polyorder})")
                self.add_history(step)
                self.current_step_index += 1
                self._update_ui_state()
                self.lbl_status.setText("Polyfit preview shown. Click Next to apply background subtraction.")
                return  # Don't update plots again

            elif step == "FluorescenceBackgroundSubtraction":
                polyorder = int(self.edit_polyorder.text())
                base, finalSpect = FluorescenceBackgroundSubtraction(
                    self.current_spect.flatten(), polyorder
                )
                self.current_spect = finalSpect
                self.operations.append(f"FBS(order={polyorder})")

            elif step == "Normalization":
                self.current_spect = Normalize(self.current_spect)
                self.operations.append("Normalization")

            else:
                QMessageBox.warning(self, "Error", f"Unknown step: {step}")
                return

            self.add_history(step)
            self.current_step_index += 1
            self._update_plots()
            self._update_ui_state()
            self.lbl_status.setText(f"Completed: {step}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Processing failed: {e}")
            # Restore previous state
            self.current_spect = self.previous_spect
            self.current_wvn = self.previous_wvn

    def on_save_figure(self):
        """Save current figure."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Figure", "spectrum_plot.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;All Files (*)"
        )
        if filepath:
            try:
                self.canvas.fig.savefig(filepath, dpi=150, bbox_inches='tight')
                self.lbl_status.setText(f"Figure saved: {filepath}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save: {e}")

    def on_save_data(self):
        """Save processed spectrum data."""
        if self.current_wvn is None or self.current_spect is None:
            QMessageBox.warning(self, "Error", "No data to save!")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Data", "processed_spectrum.csv",
            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )
        if filepath:
            try:
                wvn = self.current_wvn.reshape(-1, 1)
                spect = self.current_spect.reshape(-1, 1)
                data = np.hstack([wvn, spect])
                np.savetxt(filepath, data, delimiter=",",
                           header="Wavenumber,Intensity", comments='')
                self.lbl_status.setText(f"Data saved: {filepath}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save: {e}")

    def on_load_rdata_files(self):
        """Load spectrum, WL correction, and calibration files."""
        data_file, _ = QFileDialog.getOpenFileName(
            self, "Select Spectrum Data",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not data_file:
            return

        wlcorr_file, _ = QFileDialog.getOpenFileName(
            self, "Select WL Correction Data",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if not wlcorr_file:
            return

        wvn_file, _ = QFileDialog.getOpenFileName(
            self, "Select Calibration File (.mat)",
            "", "MAT Files (*.mat);;All Files (*)"
        )
        if not wvn_file:
            return

        try:
            # Load spectrum
            data_df = rdata.load_spectrum_data(data_file)
            self.current_spect = data_df.flatten().astype(np.float64)
            self.rawSpect = self.current_spect.copy()

            # Load WL correction
            wl_corr = rdata.read_txt_file(wlcorr_file)
            if wl_corr is None:
                raise ValueError("Failed to read WL correction file")
            self.wlCorr = wl_corr.to_numpy().astype(np.float64)

            # Load wavenumber
            self.wvnFull = rdata.getwvnfrompath(wvn_file).flatten().astype(np.float64)
            self.current_wvn = self.wvnFull.copy()

            # Reset state
            self.history = []
            self.history_list.clear()
            self.operations = []
            self.current_step_index = 1
            self.previous_spect = None
            self.previous_wvn = None

            self.operations.append("LoadData")
            self.add_history("Load Data")
            self._update_plots(show_comparison=False)
            self._update_ui_state()

            self.lbl_status.setText(
                f"Loaded: {os.path.basename(data_file)} | "
                f"Points: {len(self.current_spect)} | "
                f"Wvn range: {self.wvnFull.min():.1f} - {self.wvnFull.max():.1f} cm⁻¹"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load files: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = P_Mean_Process_UI()
    window.show()
    sys.exit(app.exec_())
