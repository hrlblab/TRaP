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
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from scipy.signal import medfilt

from UI_utils.UI_Config_Manager_v2 import ConfigManager
from UI_utils.UI_theme import get_stylesheet, Colors, Fonts
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
    """Canvas with two subplots for current view and comparison.

    Font sizes adapt automatically to canvas dimensions.
    """

    def __init__(self, parent=None, width=10, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor(Colors.BG_SECONDARY)

        # Create subplots
        self.ax_current = self.fig.add_subplot(211)
        self.ax_compare = self.fig.add_subplot(212)

        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(200, 200)

        # Crosshair state
        self._vline_current = None
        self._vline_compare = None
        self._annot_current = None
        self._annot_compare = None
        self._dot_current = None
        self._dot_compare = None
        # Stored data for snapping: (wvn_array, spect_array) or None
        self._data_current = None
        self._data_compare = None

        self._style_axes()
        self._vline_current, self._annot_current, self._dot_current = self._add_crosshair(self.ax_current)
        self._vline_compare, self._annot_compare, self._dot_compare = self._add_crosshair(self.ax_compare)

        self.mpl_connect('motion_notify_event', self._on_mouse_move)
        self.mpl_connect('axes_leave_event', self._on_axes_leave)
        self.draw()

    def sizeHint(self):
        return QSize(400, 300)

    def minimumSizeHint(self):
        return QSize(200, 200)

    def _font_sizes(self):
        """Calculate font sizes based on current canvas width."""
        w = self.width()
        title = max(9, min(16, int(w / 40)))
        label = max(8, min(13, int(w / 50)))
        tick = max(7, min(12, int(w / 55)))
        legend = max(7, min(11, int(w / 55)))
        return title, label, tick, legend

    def _style_axes(self):
        """Apply consistent dark theme styling to axes."""
        fs_title, fs_label, fs_tick, _ = self._font_sizes()
        for ax in [self.ax_current, self.ax_compare]:
            ax.set_facecolor(Colors.BG_TERTIARY)
            ax.grid(True, alpha=0.2, linestyle='--', color=Colors.BORDER)
            ax.tick_params(labelsize=fs_tick, colors=Colors.TEXT_SECONDARY)
            for spine in ax.spines.values():
                spine.set_color(Colors.BORDER)

        self.ax_current.set_title("Current Spectrum", fontsize=fs_title, fontweight='bold', color=Colors.TEXT_PRIMARY)
        self.ax_compare.set_title("Processing Comparison", fontsize=fs_title, fontweight='bold', color=Colors.TEXT_PRIMARY)
        self.fig.tight_layout(pad=2.0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-apply font sizes on resize
        fs_title, fs_label, fs_tick, fs_legend = self._font_sizes()
        for ax in [self.ax_current, self.ax_compare]:
            ax.title.set_fontsize(fs_title)
            ax.xaxis.label.set_fontsize(fs_label)
            ax.yaxis.label.set_fontsize(fs_label)
            ax.tick_params(labelsize=fs_tick)
            legend = ax.get_legend()
            if legend:
                for text in legend.get_texts():
                    text.set_fontsize(fs_legend)
        self.fig.tight_layout(pad=2.0)
        self.draw_idle()

    def _apply_ax_style(self, ax):
        """Apply dark theme styling to an axis."""
        _, _, fs_tick, _ = self._font_sizes()
        ax.set_facecolor(Colors.BG_TERTIARY)
        ax.grid(True, alpha=0.2, linestyle='--', color=Colors.BORDER)
        ax.tick_params(labelsize=fs_tick, colors=Colors.TEXT_SECONDARY)
        for spine in ax.spines.values():
            spine.set_color(Colors.BORDER)

    def _add_crosshair(self, ax):
        """Add invisible crosshair elements to an axis. Returns (vline, annot, dot)."""
        vline = ax.axvline(x=0, color='#888888', linewidth=0.8,
                           linestyle='--', alpha=0.6, visible=False)
        annot = ax.annotate(
            '', xy=(0, 0), xytext=(12, 12),
            textcoords='offset points',
            ha='left', va='bottom',
            fontsize=8,
            color=Colors.TEXT_PRIMARY,
            bbox=dict(boxstyle='round,pad=0.4',
                      facecolor=Colors.BG_DARK,
                      edgecolor=Colors.BORDER,
                      alpha=0.88),
            visible=False
        )
        dot, = ax.plot([], [], 'o', color='#F0A500',
                       markersize=5, zorder=5, visible=False)
        return vline, annot, dot

    def _snap_to_data(self, data, x_mouse):
        """Find the nearest data point to x_mouse. Returns (x_snap, y_snap) or None."""
        if data is None:
            return None
        wvn, spect = data
        if wvn is None or len(wvn) == 0:
            return None
        idx = int(np.argmin(np.abs(wvn - x_mouse)))
        return wvn[idx], spect[idx]

    def _on_mouse_move(self, event):
        if event.inaxes == self.ax_current:
            vline, annot, dot = self._vline_current, self._annot_current, self._dot_current
            data = self._data_current
        elif event.inaxes == self.ax_compare:
            vline, annot, dot = self._vline_compare, self._annot_compare, self._dot_compare
            data = self._data_compare
        else:
            return
        if vline is None or annot is None or event.xdata is None:
            return

        snap = self._snap_to_data(data, event.xdata)
        if snap is not None:
            x_snap, y_snap = snap
            vline.set_xdata([x_snap, x_snap])
            vline.set_visible(True)
            annot.set_text(f'Wvn: {x_snap:.1f} cm⁻¹\nI: {y_snap:.4f}')
            annot.xy = (x_snap, y_snap)
            # Flip offset when near right or top edge
            ax = event.inaxes
            xlim, ylim = ax.get_xlim(), ax.get_ylim()
            x_frac = (x_snap - xlim[0]) / (xlim[1] - xlim[0]) if xlim[1] != xlim[0] else 0.5
            y_frac = (y_snap - ylim[0]) / (ylim[1] - ylim[0]) if ylim[1] != ylim[0] else 0.5
            ox = -70 if x_frac > 0.75 else 12
            oy = -30 if y_frac > 0.75 else 12
            annot.xyann = (ox, oy)
            annot.set_ha('right' if x_frac > 0.75 else 'left')
            annot.set_va('top' if y_frac > 0.75 else 'bottom')
            annot.set_visible(True)
            if dot is not None:
                dot.set_data([x_snap], [y_snap])
                dot.set_visible(True)
        else:
            vline.set_xdata([event.xdata, event.xdata])
            vline.set_visible(True)
            annot.set_text(f'Wvn: {event.xdata:.1f}\nI: {event.ydata:.4f}')
            annot.xy = (event.xdata, event.ydata)
            annot.set_visible(True)
        self.draw_idle()

    def _on_axes_leave(self, event):
        if event.inaxes == self.ax_current:
            for artist in [self._vline_current, self._annot_current, self._dot_current]:
                if artist is not None:
                    artist.set_visible(False)
        elif event.inaxes == self.ax_compare:
            for artist in [self._vline_compare, self._annot_compare, self._dot_compare]:
                if artist is not None:
                    artist.set_visible(False)
        self.draw_idle()

    def plot_current(self, wvn, spect, title=None):
        """Plot the current spectrum state."""
        fs_title, fs_label, _, fs_legend = self._font_sizes()
        self.ax_current.clear()
        self._apply_ax_style(self.ax_current)
        if wvn is not None and len(wvn) == len(spect):
            self.ax_current.plot(wvn, spect, color=Colors.PRIMARY, linewidth=1.5, label='Current')
            self.ax_current.set_xlabel("Wavenumber (cm$^{-1}$)", fontsize=fs_label, color=Colors.TEXT_SECONDARY)
        else:
            self.ax_current.plot(spect, color=Colors.PRIMARY, linewidth=1.5, label='Current')
            self.ax_current.set_xlabel("Index", fontsize=fs_label, color=Colors.TEXT_SECONDARY)

        self.ax_current.set_ylabel("Intensity", fontsize=fs_label, color=Colors.TEXT_SECONDARY)
        self.ax_current.set_title(title or "Current Spectrum", fontsize=fs_title, fontweight='bold', color=Colors.TEXT_PRIMARY)
        self.ax_current.legend(loc='best', fontsize=fs_legend, facecolor=Colors.BG_TERTIARY, edgecolor=Colors.BORDER, labelcolor=Colors.TEXT_PRIMARY)
        if wvn is not None and len(wvn) == len(spect):
            self._data_current = (np.asarray(wvn), np.asarray(spect))
        else:
            self._data_current = (np.arange(len(spect), dtype=float), np.asarray(spect))
        self._vline_current, self._annot_current, self._dot_current = self._add_crosshair(self.ax_current)
        x = self._data_current[0]
        self.ax_current.set_xlim(x[0], x[-1])
        self.fig.tight_layout(pad=2.0)
        self.draw()

    def plot_comparison(self, wvn, before, after, before_label="Before", after_label="After"):
        """Plot before/after comparison."""
        fs_title, fs_label, _, fs_legend = self._font_sizes()
        self.ax_compare.clear()
        self._apply_ax_style(self.ax_compare)

        if wvn is not None and len(wvn) == len(before):
            self.ax_compare.plot(wvn, before, color=Colors.TEXT_TERTIARY, linewidth=1.2, alpha=0.7, label=before_label)
            if after is not None and len(after) == len(wvn):
                self.ax_compare.plot(wvn, after, color=Colors.SUCCESS, linewidth=1.5, label=after_label)
            self.ax_compare.set_xlabel("Wavenumber (cm$^{-1}$)", fontsize=fs_label, color=Colors.TEXT_SECONDARY)
        else:
            self.ax_compare.plot(before, color=Colors.TEXT_TERTIARY, linewidth=1.2, alpha=0.7, label=before_label)
            if after is not None:
                self.ax_compare.plot(after, color=Colors.SUCCESS, linewidth=1.5, label=after_label)
            self.ax_compare.set_xlabel("Index", fontsize=fs_label, color=Colors.TEXT_SECONDARY)

        self.ax_compare.set_ylabel("Intensity", fontsize=fs_label, color=Colors.TEXT_SECONDARY)
        self.ax_compare.set_title("Processing Comparison", fontsize=fs_title, fontweight='bold', color=Colors.TEXT_PRIMARY)
        self.ax_compare.legend(loc='best', fontsize=fs_legend, facecolor=Colors.BG_TERTIARY, edgecolor=Colors.BORDER, labelcolor=Colors.TEXT_PRIMARY)
        snap_spect = after if (after is not None and wvn is not None and len(after) == len(wvn)) else before
        if wvn is not None and len(wvn) == len(snap_spect):
            self._data_compare = (np.asarray(wvn), np.asarray(snap_spect))
        else:
            self._data_compare = (np.arange(len(snap_spect), dtype=float), np.asarray(snap_spect))
        self._vline_compare, self._annot_compare, self._dot_compare = self._add_crosshair(self.ax_compare)
        x = self._data_compare[0]
        self.ax_compare.set_xlim(x[0], x[-1])
        self.fig.tight_layout(pad=2.0)
        self.draw()

    def plot_polyfit(self, wvn, spect, baseline):
        """Plot spectrum with polyfit baseline."""
        fs_title, fs_label, _, fs_legend = self._font_sizes()
        self.ax_compare.clear()
        self._apply_ax_style(self.ax_compare)

        if wvn is not None and len(wvn) == len(spect):
            self.ax_compare.plot(wvn, spect, color=Colors.PRIMARY, linewidth=1.5, label='Spectrum')
            self.ax_compare.plot(wvn, baseline, color=Colors.DANGER, linestyle='--', linewidth=1.8, label='Polyfit Baseline')
            self.ax_compare.set_xlabel("Wavenumber (cm$^{-1}$)", fontsize=fs_label, color=Colors.TEXT_SECONDARY)
        else:
            self.ax_compare.plot(spect, color=Colors.PRIMARY, linewidth=1.5, label='Spectrum')
            self.ax_compare.plot(baseline, color=Colors.DANGER, linestyle='--', linewidth=1.8, label='Polyfit Baseline')
            self.ax_compare.set_xlabel("Index", fontsize=fs_label, color=Colors.TEXT_SECONDARY)

        self.ax_compare.set_ylabel("Intensity", fontsize=fs_label, color=Colors.TEXT_SECONDARY)
        self.ax_compare.set_title("Polyfit Baseline Preview", fontsize=fs_title, fontweight='bold', color=Colors.TEXT_PRIMARY)
        self.ax_compare.legend(loc='best', fontsize=fs_legend, facecolor=Colors.BG_TERTIARY, edgecolor=Colors.BORDER, labelcolor=Colors.TEXT_PRIMARY)
        self.ax_compare.fill_between(
            wvn if wvn is not None and len(wvn) == len(spect) else range(len(spect)),
            baseline, spect, alpha=0.2, color=Colors.SUCCESS, label='Background'
        )
        if wvn is not None and len(wvn) == len(spect):
            self._data_compare = (np.asarray(wvn), np.asarray(spect))
        else:
            self._data_compare = (np.arange(len(spect), dtype=float), np.asarray(spect))
        self._vline_compare, self._annot_compare, self._dot_compare = self._add_crosshair(self.ax_compare)
        x = self._data_compare[0]
        self.ax_compare.set_xlim(x[0], x[-1])
        self.fig.tight_layout(pad=2.0)
        self.draw()


class StepIndicator(QWidget):
    """Visual step progress indicator.

    Current and next steps show full name; others show only the step number.
    """

    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self.steps = steps
        self.current_index = 0
        self.step_labels = []  # list of (frame, label, index)
        self._build_ui()

    def _build_ui(self):
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(3)

        for i, step in enumerate(self.steps):
            frame = QFrame()
            frame.setFixedHeight(38)
            frame_layout = QHBoxLayout(frame)
            frame_layout.setContentsMargins(6, 3, 6, 3)

            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            label.setToolTip(f"Step {i}: {step}")
            frame_layout.addWidget(label)

            self.step_labels.append((frame, label, i))
            self._layout.addWidget(frame)

        self._update_styles()

    def _update_styles(self):
        for frame, label, i in self.step_labels:
            # Determine if this step should show full text
            is_focus = (i == self.current_index or i == self.current_index + 1)

            if is_focus:
                label.setText(f"{i}. {self.steps[i]}")
                frame.setMinimumWidth(0)
            else:
                label.setText(f"{i}")
                frame.setFixedWidth(32)

            if i < self.current_index:
                # Completed
                frame.setStyleSheet(
                    f"background-color: {Colors.SUCCESS}; border-radius: 6px; "
                    f"border: 2px solid {Colors.SUCCESS};"
                )
                label.setStyleSheet(
                    f"color: {Colors.BG_DARK}; font-weight: bold; "
                    f"font-size: {Fonts.SIZE_SM}px;"
                )
            elif i == self.current_index:
                # Current — highlighted
                frame.setStyleSheet(
                    f"background-color: {Colors.PRIMARY}; border-radius: 6px; "
                    f"border: 2px solid #79C0FF;"
                )
                label.setStyleSheet(
                    f"color: {Colors.BG_DARK}; font-weight: bold; "
                    f"font-size: {Fonts.SIZE_SM}px;"
                )
            elif i == self.current_index + 1:
                # Next step — slightly highlighted
                frame.setStyleSheet(
                    f"background-color: {Colors.BG_TERTIARY}; border-radius: 6px; "
                    f"border: 2px solid {Colors.PRIMARY};"
                )
                label.setStyleSheet(
                    f"color: {Colors.TEXT_PRIMARY}; font-weight: bold; "
                    f"font-size: {Fonts.SIZE_SM}px;"
                )
            else:
                # Other pending
                frame.setStyleSheet(
                    f"background-color: {Colors.BG_TERTIARY}; border-radius: 6px; "
                    f"border: 1px solid {Colors.BORDER};"
                )
                label.setStyleSheet(
                    f"color: {Colors.TEXT_TERTIARY}; "
                    f"font-size: {Fonts.SIZE_SM}px;"
                )

            # Reset width constraint for focus steps
            if is_focus:
                frame.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX
                frame.setMinimumWidth(0)

    def set_step(self, index):
        self.current_index = min(max(0, index), len(self.steps))
        self._update_styles()


class P_Mean_Process_UI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_system = config_manager.params.get("System", "")

        self.setWindowTitle("Spectrum Data Process - Enhanced")
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1400, int(screen.width() * 0.9)), min(900, int(screen.height() * 0.9)))
        self.move(screen.center() - self.rect().center())
        # Apply unified dark theme
        self.setStyleSheet(get_stylesheet())

        # Data state
        self.wvnFull = np.zeros([100, 1])
        self.rawSpect = np.zeros(self.wvnFull.shape)
        self.current_spect = self.rawSpect.copy()
        self.current_wvn = self.wvnFull.copy()
        self.previous_spect = None  # For comparison
        self.previous_wvn = None
        self.wlCorr = np.ones((500, 1)) * 1.2

        # File paths for independent upload
        self.data_file = None
        self.wlcorr_file = None
        self.calibration_file = None

        self.operations = []
        self.history = []
        self.processing_steps = [
            "Load Data",
            "SubtractBaseline",
            "SpectralResponseCorrection",
            "CosmicRayRemoval",
            "Truncate",
            "Binning",
            "Polyfit Preview",
            "FluorescenceBackgroundSubtraction",
            "Noise Smoothing",
            "Normalization"
        ]
        self.current_step_index = 0

        self._build_ui()
        self._update_ui_state()
        self._update_file_widgets_visibility()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Use QSplitter so user can drag to resize panels
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left panel - Controls (scrollable)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(250)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        # Step indicator (scrollable)
        step_scroll = QScrollArea()
        step_scroll.setWidgetResizable(True)
        step_scroll.setFixedHeight(56)
        step_scroll.setFrameShape(QFrame.NoFrame)
        step_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.step_indicator = StepIndicator(self.processing_steps)
        step_scroll.setWidget(self.step_indicator)
        left_layout.addWidget(step_scroll)

        # Current step info
        self.lbl_step_info = QLabel("Step 0: Load Data")
        self.lbl_step_info.setStyleSheet("font-size: 14px; font-weight: bold; color: #007bff; padding: 5px;")
        left_layout.addWidget(self.lbl_step_info)

        # ── Processing Parameters (grouped by pipeline step) ──────────────
        params_group = QGroupBox("Processing Parameters")
        params_outer = QVBoxLayout(params_group)
        params_outer.setSpacing(8)

        STEP_STYLE = "color: #4C8BF5; font-size: 11px; font-weight: 600; padding: 2px 0 1px 0;"

        def make_field(default, width=80):
            w = QLineEdit(default)
            w.setMinimumHeight(32)
            w.setMaximumWidth(width)
            return w

        def add_step_header(layout, label):
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet("color: #2a2a2a;")
            layout.addWidget(sep)
            lbl = QLabel(label)
            lbl.setStyleSheet(STEP_STYLE)
            layout.addWidget(lbl)

        def add_row(layout, label_text, widget):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setMinimumWidth(130)
            row.addWidget(lbl)
            row.addWidget(widget)
            row.addStretch()
            layout.addLayout(row)

        # Truncation
        add_step_header(params_outer, "Truncation")
        self.edit_start = make_field("900")
        self.edit_stop  = make_field("1700")
        add_row(params_outer, "Start (cm⁻¹):", self.edit_start)
        add_row(params_outer, "Stop  (cm⁻¹):", self.edit_stop)

        # Binning
        add_step_header(params_outer, "Binning")
        self.edit_binwidth = make_field("3.5")
        add_row(params_outer, "Bin Width (cm⁻¹):", self.edit_binwidth)

        # Noise Smoothing
        add_step_header(params_outer, "Noise Smoothing")
        self.combo_denoise = QComboBox()
        self.combo_denoise.addItems(["Savitzky-Golay", "Moving Average", "Median Filter", "None"])
        self.combo_denoise.currentTextChanged.connect(self._update_denoise_visibility)
        self.combo_denoise.setMinimumHeight(32)
        add_row(params_outer, "Method:", self.combo_denoise)

        self.edit_sgorder  = make_field("2")
        self.edit_sgframe  = make_field("7")
        self.edit_mawindow = make_field("5")
        self.edit_mediank  = make_field("5")

        def make_row_widget(label_text, field):
            """Wrap a label+field in a QWidget so we can hide the whole row."""
            w = QWidget()
            row = QHBoxLayout(w)
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label_text)
            lbl.setMinimumWidth(130)
            row.addWidget(lbl)
            row.addWidget(field)
            row.addStretch()
            return w

        self.row_sgorder  = make_row_widget("SG Poly Order:", self.edit_sgorder)
        self.row_sgframe  = make_row_widget("SG Window Size:", self.edit_sgframe)
        self.row_mawindow = make_row_widget("MA Window:", self.edit_mawindow)
        self.row_mediank  = make_row_widget("Median Kernel:", self.edit_mediank)

        for row_w in [self.row_sgorder, self.row_sgframe, self.row_mawindow, self.row_mediank]:
            params_outer.addWidget(row_w)

        # Fluorescence BG Subtraction
        add_step_header(params_outer, "Fluorescence BG Subtraction")
        self.edit_polyorder = make_field("7")
        self.edit_fbs_maxiter = make_field("50")
        add_row(params_outer, "Poly Order:", self.edit_polyorder)
        add_row(params_outer, "Max Iterations:", self.edit_fbs_maxiter)

        # Normalization
        add_step_header(params_outer, "Normalization")
        self.combo_norm = QComboBox()
        self.combo_norm.addItems(["Mean", "Max", "Area"])
        self.combo_norm.setMinimumHeight(32)
        add_row(params_outer, "Method:", self.combo_norm)

        self._update_denoise_visibility()

        # Config Group (build here, added to layout after files+params)
        config_group = QGroupBox("Configuration")
        config_layout = QHBoxLayout(config_group)
        config_layout.setSpacing(8)
        btn_save_config = QPushButton("Save Config")
        btn_save_config.clicked.connect(self.on_save_config)
        btn_save_config.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_load_config = QPushButton("Load Config")
        btn_load_config.clicked.connect(self.on_load_config)
        btn_load_config.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        config_layout.addWidget(btn_save_config)
        config_layout.addWidget(btn_load_config)

        # Input Files Group
        files_group = QGroupBox("Input Files")
        files_layout = QVBoxLayout(files_group)
        files_layout.setSpacing(8)

        # System info label
        is_renishaw = self._is_renishaw_system()
        system_text = f"System: {self.current_system}"
        if is_renishaw:
            system_text += " (WL Correction & Calibration not required)"
        self.lbl_system_info = QLabel(system_text)
        self.lbl_system_info.setWordWrap(True)
        self.lbl_system_info.setStyleSheet(
            f"color: {Colors.SUCCESS}; font-weight: bold; padding: 8px; "
            f"background-color: {Colors.BG_TERTIARY}; border-radius: 6px;"
            if is_renishaw else
            f"color: {Colors.PRIMARY}; font-weight: bold; padding: 8px; "
            f"background-color: {Colors.BG_TERTIARY}; border-radius: 6px;"
        )
        files_layout.addWidget(self.lbl_system_info)

        # Spectrum Data file upload
        data_layout = QHBoxLayout()
        data_layout.setSpacing(8)
        self.btn_select_data = QPushButton("Select Spectrum Data")
        self.btn_select_data.clicked.connect(self.on_select_data_file)
        self.btn_select_data.setMinimumWidth(160)
        data_layout.addWidget(self.btn_select_data)
        self.lbl_data_file = QLabel("Not selected")
        self.lbl_data_file.setStyleSheet(f"color: {Colors.DANGER};")
        self.lbl_data_file.setWordWrap(True)
        data_layout.addWidget(self.lbl_data_file, 1)
        files_layout.addLayout(data_layout)

        # WL Correction file upload (container for visibility control)
        self.wl_widget = QWidget()
        wl_layout = QHBoxLayout(self.wl_widget)
        wl_layout.setContentsMargins(0, 0, 0, 0)
        wl_layout.setSpacing(8)
        self.btn_select_wlcorr = QPushButton("Select WL Correction")
        self.btn_select_wlcorr.clicked.connect(self.on_select_wlcorr_file)
        self.btn_select_wlcorr.setMinimumWidth(160)
        wl_layout.addWidget(self.btn_select_wlcorr)
        self.lbl_wlcorr_file = QLabel("Not selected")
        self.lbl_wlcorr_file.setStyleSheet(f"color: {Colors.DANGER};")
        self.lbl_wlcorr_file.setWordWrap(True)
        wl_layout.addWidget(self.lbl_wlcorr_file, 1)
        files_layout.addWidget(self.wl_widget)

        # Calibration file upload (container for visibility control)
        self.cal_widget = QWidget()
        cal_layout = QHBoxLayout(self.cal_widget)
        cal_layout.setContentsMargins(0, 0, 0, 0)
        cal_layout.setSpacing(8)
        self.btn_select_cal = QPushButton("Select Calibration (.mat)")
        self.btn_select_cal.clicked.connect(self.on_select_calibration_file)
        self.btn_select_cal.setMinimumWidth(160)
        cal_layout.addWidget(self.btn_select_cal)
        self.lbl_cal_file = QLabel("Not selected")
        self.lbl_cal_file.setStyleSheet(f"color: {Colors.DANGER};")
        self.lbl_cal_file.setWordWrap(True)
        cal_layout.addWidget(self.lbl_cal_file, 1)
        files_layout.addWidget(self.cal_widget)

        # Load button lives inside Input Files
        self.btn_load = QPushButton("Load && Process Data")
        self.btn_load.setProperty("class", "success")
        self.btn_load.clicked.connect(self.on_load_rdata_files)
        self.btn_load.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        files_layout.addWidget(self.btn_load)

        # Input Files goes first
        left_layout.addWidget(files_group)
        left_layout.addWidget(params_group)

        # Navigation Group
        nav_group = QGroupBox("Navigation")
        nav_layout = QVBoxLayout(nav_group)
        nav_layout.setSpacing(8)

        # Step navigation
        step_nav = QHBoxLayout()
        step_nav.setSpacing(8)
        self.btn_previous = QPushButton("< Previous")
        self.btn_previous.clicked.connect(self.on_previous_step)
        self.btn_previous.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_next = QPushButton("Next >")
        self.btn_next.clicked.connect(self.on_next_step)
        self.btn_next.setProperty("class", "primary")
        self.btn_next.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        step_nav.addWidget(self.btn_previous)
        step_nav.addWidget(self.btn_next)
        nav_layout.addLayout(step_nav)

        # Save buttons
        save_layout = QHBoxLayout()
        save_layout.setSpacing(8)
        self.btn_save_fig = QPushButton("Save Figure")
        self.btn_save_fig.clicked.connect(self.on_save_figure)
        self.btn_save_fig.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_save_data = QPushButton("Save Data")
        self.btn_save_data.clicked.connect(self.on_save_data)
        self.btn_save_data.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        save_layout.addWidget(self.btn_save_fig)
        save_layout.addWidget(self.btn_save_data)
        nav_layout.addLayout(save_layout)

        # Switch to Batch Process button
        self.btn_batch = QPushButton("Switch to Batch Process")
        self.btn_batch.setProperty("class", "info")
        self.btn_batch.setToolTip("Open Batch Processing for multiple files")
        self.btn_batch.clicked.connect(self.on_switch_to_batch)
        self.btn_batch.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_layout.addWidget(self.btn_batch)

        left_layout.addWidget(config_group)
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
        self.lbl_status.setStyleSheet(
            f"padding: 5px; background-color: {Colors.BG_TERTIARY}; "
            f"color: {Colors.TEXT_SECONDARY}; border-radius: 3px; "
            f"border: 1px solid {Colors.BORDER};"
        )
        right_layout.addWidget(self.lbl_status)

        # Add to splitter
        left_scroll.setWidget(left_panel)
        splitter.addWidget(left_scroll)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)  # Left panel: don't stretch
        splitter.setStretchFactor(1, 1)  # Right panel: stretch
        splitter.setSizes([360, 640])
        main_layout.addWidget(splitter)

    def _update_denoise_visibility(self):
        """Show/hide denoise parameters based on selected method."""
        method = self.combo_denoise.currentText()
        is_sg  = method == "Savitzky-Golay"
        is_ma  = method == "Moving Average"
        is_med = method == "Median Filter"

        self.row_sgorder.setVisible(is_sg)
        self.row_sgframe.setVisible(is_sg)
        self.row_mawindow.setVisible(is_ma)
        self.row_mediank.setVisible(is_med)

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
            config["FBSMaxIter"] = int(self.edit_fbs_maxiter.text())
            config["NormalizeMethod"] = self.combo_norm.currentText()
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
                    raw = f.read()
                try:
                    config = json.loads(raw)
                except json.JSONDecodeError as e:
                    QMessageBox.critical(self, "Invalid JSON", f"Config file is not valid JSON:\n{e}")
                    return
                if not isinstance(config, dict):
                    QMessageBox.critical(self, "Invalid Config", "Config file must be a JSON object.")
                    return

                # Field-level validation
                VALID_DENOISE   = {"Savitzky-Golay", "Moving Average", "Median Filter", "None"}
                VALID_NORMALIZE = {"Mean", "Max", "Area"}
                warnings = []
                def checked_float(key, default, min_val=None):
                    try:
                        v = float(config.get(key, default))
                        if min_val is not None and v <= min_val:
                            warnings.append(f"{key} must be > {min_val} (got {v}), using default {default}")
                            return default
                        return v
                    except (TypeError, ValueError):
                        warnings.append(f"{key} is not a valid number (got {config.get(key)!r}), using default {default}")
                        return default
                def checked_int(key, default, min_val=None):
                    try:
                        v = int(config.get(key, default))
                        if min_val is not None and v < min_val:
                            warnings.append(f"{key} must be >= {min_val} (got {v}), using default {default}")
                            return default
                        return v
                    except (TypeError, ValueError):
                        warnings.append(f"{key} is not a valid integer (got {config.get(key)!r}), using default {default}")
                        return default

                start    = checked_float("Start",    900,  0)
                stop     = checked_float("Stop",     1700, 0)
                if stop <= start:
                    warnings.append(f"Stop ({stop}) must be > Start ({start}), using defaults")
                    start, stop = 900, 1700
                binwidth = checked_float("BinWidth",  3.5,  0)
                poly     = checked_int("Polyorder",   7,    1)
                maxiter  = checked_int("FBSMaxIter",  50,   1)
                sgorder  = checked_int("SGorder",     2,    1)
                sgframe  = checked_int("SGframe",     7,    3)
                if sgframe % 2 == 0:
                    warnings.append(f"SGframe must be odd (got {sgframe}), incrementing to {sgframe+1}")
                    sgframe += 1
                mawin    = checked_int("MAWindow",    5,    1)
                medk     = checked_int("MedianKernel",5,    1)
                dn       = config.get("DenoiseMethod", "Savitzky-Golay")
                if dn not in VALID_DENOISE:
                    warnings.append(f"DenoiseMethod {dn!r} not recognised, using 'Savitzky-Golay'")
                    dn = "Savitzky-Golay"
                nm       = config.get("NormalizeMethod", "Mean")
                if nm not in VALID_NORMALIZE:
                    warnings.append(f"NormalizeMethod {nm!r} not recognised, using 'Mean'")
                    nm = "Mean"

                if warnings:
                    QMessageBox.warning(self, "Config Warnings",
                                        "Loaded with issues:\n• " + "\n• ".join(warnings))

                self.edit_start.setText(str(start))
                self.edit_stop.setText(str(stop))
                self.edit_binwidth.setText(str(binwidth))
                self.edit_polyorder.setText(str(poly))
                self.edit_fbs_maxiter.setText(str(maxiter))
                self.combo_norm.setCurrentText(nm)
                self.combo_denoise.setCurrentText(dn)
                self.edit_sgorder.setText(str(sgorder))
                self.edit_sgframe.setText(str(sgframe))
                self.edit_mawindow.setText(str(mawin))
                self.edit_mediank.setText(str(medk))
                self.lbl_status.setText(f"Config loaded: {filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load config:\n{e}")

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
                if self._is_renishaw_system():
                    # Skip spectral response correction for Renishaw system
                    self.operations.append("SpectralResponseCorrection(Skipped-Renishaw)")
                    self.lbl_status.setText("SpectralResponseCorrection skipped for Renishaw system.")
                else:
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

            elif step == "Polyfit Preview":
                polyorder = int(self.edit_polyorder.text())
                fbs_maxiter = int(self.edit_fbs_maxiter.text())
                base, _ = FluorescenceBackgroundSubtraction(self.current_spect.flatten(), polyorder, max_iter=fbs_maxiter)
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
                fbs_maxiter = int(self.edit_fbs_maxiter.text())
                base, finalSpect = FluorescenceBackgroundSubtraction(
                    self.current_spect.flatten(), polyorder, max_iter=fbs_maxiter
                )
                self.current_spect = finalSpect
                self.operations.append(f"FBS(order={polyorder},iter={fbs_maxiter})")

            elif step == "Noise Smoothing":
                method = self.combo_denoise.currentText()
                if method == "Savitzky-Golay":
                    sg_order = int(self.edit_sgorder.text())
                    sg_frame = int(self.edit_sgframe.text())
                    if sg_frame < 3 or sg_frame % 2 == 0:
                        QMessageBox.warning(self, "Error", "SGframe must be odd >= 3!")
                        return
                    self.current_spect = Denoise(self.current_spect, SGorder=sg_order, SGframe=sg_frame)
                    self.operations.append(f"NoiseSmoothing(SG,o={sg_order},f={sg_frame})")
                elif method == "Moving Average":
                    w = int(self.edit_mawindow.text())
                    self.current_spect = moving_average(self.current_spect.flatten(), window=w)
                    self.operations.append(f"NoiseSmoothing(MA,w={w})")
                elif method == "Median Filter":
                    k = int(self.edit_mediank.text())
                    self.current_spect = median_filter(self.current_spect.flatten(), kernel_size=k)
                    self.operations.append(f"NoiseSmoothing(Med,k={k})")
                else:
                    self.operations.append("NoiseSmoothing(None)")

            elif step == "Normalization":
                norm_method = self.combo_norm.currentText().lower()
                self.current_spect = Normalize(self.current_spect, method=norm_method)
                self.operations.append(f"Normalization({norm_method})")

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

    def _is_renishaw_system(self):
        """Check if the current system is Renishaw."""
        return self.current_system.lower() == "renishaw"

    def _update_file_widgets_visibility(self):
        """Show/hide WL Correction and Calibration widgets based on system type."""
        is_renishaw = self._is_renishaw_system()
        self.wl_widget.setVisible(not is_renishaw)
        self.cal_widget.setVisible(not is_renishaw)

    def on_select_data_file(self):
        """Select spectrum data file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Spectrum Data",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if file_path:
            self.data_file = file_path
            self.lbl_data_file.setText(os.path.basename(file_path))
            self.lbl_data_file.setStyleSheet(f"color: {Colors.SUCCESS};")
            self.lbl_status.setText(f"Data file selected: {os.path.basename(file_path)}")

    def on_select_wlcorr_file(self):
        """Select WL Correction file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select WL Correction Data",
            "", "Data Files (*.txt *.csv *.xlsx);;All Files (*)"
        )
        if file_path:
            self.wlcorr_file = file_path
            self.lbl_wlcorr_file.setText(os.path.basename(file_path))
            self.lbl_wlcorr_file.setStyleSheet(f"color: {Colors.SUCCESS};")
            self.lbl_status.setText(f"WL Correction file selected: {os.path.basename(file_path)}")

    def on_select_calibration_file(self):
        """Select Calibration (.mat) file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Calibration File (.mat)",
            "", "MAT Files (*.mat);;All Files (*)"
        )
        if file_path:
            self.calibration_file = file_path
            self.lbl_cal_file.setText(os.path.basename(file_path))
            self.lbl_cal_file.setStyleSheet(f"color: {Colors.SUCCESS};")
            self.lbl_status.setText(f"Calibration file selected: {os.path.basename(file_path)}")

    def on_load_rdata_files(self):
        """Load spectrum data files using the independently selected files.
        For Renishaw, only data file is needed.
        For other systems, WL correction and calibration files are also required."""

        is_renishaw = self._is_renishaw_system()

        # Validate that required files are selected
        if not self.data_file:
            QMessageBox.warning(self, "Error", "Please select a spectrum data file first.")
            return

        if not is_renishaw:
            if not self.wlcorr_file:
                QMessageBox.warning(self, "Error", "Please select a WL Correction file.")
                return
            if not self.calibration_file:
                QMessageBox.warning(self, "Error", "Please select a Calibration (.mat) file.")
                return

        try:
            if is_renishaw:
                # Renishaw: Data file contains both wavenumber and intensity (2 columns)
                # Use read_txt_file to preserve both columns (load_spectrum_data strips wavenumber)
                data_df = rdata.read_txt_file(self.data_file)
                data_arr = data_df.to_numpy().astype(np.float64)

                if data_arr.ndim == 2 and data_arr.shape[1] >= 2:
                    # Two-column format: [wavenumber, intensity]
                    self.wvnFull = data_arr[:, 0].flatten()
                    self.current_spect = data_arr[:, 1].flatten()
                else:
                    # Single column - use index as x-axis
                    self.current_spect = data_arr.flatten()
                    self.wvnFull = np.arange(len(self.current_spect), dtype=np.float64)

                self.rawSpect = self.current_spect.copy()
                self.current_wvn = self.wvnFull.copy()
                # Renishaw doesn't need WL correction
                self.wlCorr = np.ones_like(self.current_spect).reshape(-1, 1)

            else:
                # Non-Renishaw: Load three separate files
                # Load spectrum
                data_df = rdata.load_spectrum_data(self.data_file)
                self.current_spect = data_df.flatten().astype(np.float64)
                self.rawSpect = self.current_spect.copy()

                # Load WL correction
                wl_corr = rdata.read_txt_file(self.wlcorr_file)
                if wl_corr is None:
                    raise ValueError("Failed to read WL correction file")
                self.wlCorr = wl_corr.to_numpy().astype(np.float64)

                # Load wavenumber from calibration file
                self.wvnFull = rdata.getwvnfrompath(self.calibration_file).flatten().astype(np.float64)
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

            system_info = " (Renishaw - no WL/Cal needed)" if is_renishaw else ""
            self.lbl_status.setText(
                f"Loaded: {os.path.basename(self.data_file)}{system_info} | "
                f"Points: {len(self.current_spect)} | "
                f"Wvn range: {self.wvnFull.min():.1f} - {self.wvnFull.max():.1f} cm⁻¹"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load files: {e}")

    def on_switch_to_batch(self):
        """Open Batch Processing window."""
        # Use lazy import to avoid circular import issues
        from UI_utils.UI_P_Mean_Batch_Process import BatchPMeanUI

        self.batch_window = BatchPMeanUI()
        self.batch_window.show()
        self.lbl_status.setText("Batch Processing window opened.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = P_Mean_Process_UI()
    window.show()
    sys.exit(app.exec_())
