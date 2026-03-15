#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch P_Mean UI - Enhanced Version

Features:
- Progress bar with detailed status
- Preview first file before batch processing
- Auto-save config prompt on close
- Processing log with export capability
- Improved parameter validation
"""

import sys
import os
import json
from datetime import datetime
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QMessageBox, QListWidget, QLineEdit,
    QComboBox, QGroupBox, QFormLayout, QProgressBar, QTextEdit,
    QSplitter, QSizePolicy, QCheckBox, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QTextCursor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.io import wdata, rdata
from utils.SpectralPreprocess import (
    Binning, Denoise, Truncate, CosmicRayRemoval,
    SpectralResponseCorrection, subtractBaseline,
    FluorescenceBackgroundSubtraction, Normalize
)
from UI_utils.UI_Config_Manager_v2 import ConfigManager
from UI_utils.UI_theme import get_stylesheet, Colors, Fonts


VALID_DENOISE   = {"Savitzky-Golay", "Moving Average", "Median Filter", "None"}
VALID_NORMALIZE = {"Mean", "Max", "Area"}

def default_config() -> dict:
    """Return default configuration."""
    return {
        "Start": 900,
        "Stop": 1700,
        "Polyorder": 7,
        "FBSMaxIter": 50,
        "NormalizeMethod": "Mean",
        "DenoiseMethod": "Savitzky-Golay",
        "BinWidth": 3.5,
        "SGorder": 2,
        "SGframe": 7,
        "MAWindow": 5,
        "MedianKernel": 5
    }


def validate_config(cfg: dict) -> list:
    """Check config fields for type/range validity. Returns list of error strings."""
    errors = []
    defaults = default_config()

    def check_positive_float(key):
        try:
            v = float(cfg.get(key, defaults[key]))
            if v <= 0:
                errors.append(f"{key} must be > 0 (got {v})")
        except (TypeError, ValueError):
            errors.append(f"{key} must be a number (got {cfg.get(key)!r})")

    def check_positive_int(key):
        try:
            v = int(cfg.get(key, defaults[key]))
            if v <= 0:
                errors.append(f"{key} must be a positive integer (got {v})")
        except (TypeError, ValueError):
            errors.append(f"{key} must be an integer (got {cfg.get(key)!r})")

    check_positive_float("Start")
    check_positive_float("Stop")
    check_positive_float("BinWidth")
    check_positive_int("Polyorder")
    check_positive_int("FBSMaxIter")
    check_positive_int("SGorder")
    check_positive_int("SGframe")
    check_positive_int("MAWindow")
    check_positive_int("MedianKernel")

    try:
        start, stop = float(cfg.get("Start", 900)), float(cfg.get("Stop", 1700))
        if stop <= start:
            errors.append(f"Stop ({stop}) must be > Start ({start})")
    except (TypeError, ValueError):
        pass

    dn = cfg.get("DenoiseMethod", "Savitzky-Golay")
    if dn not in VALID_DENOISE:
        errors.append(f"DenoiseMethod {dn!r} not recognised. Valid: {VALID_DENOISE}")

    nm = cfg.get("NormalizeMethod", "Mean")
    if nm not in VALID_NORMALIZE:
        errors.append(f"NormalizeMethod {nm!r} not recognised. Valid: {VALID_NORMALIZE}")

    sg_frame = cfg.get("SGframe", 7)
    sg_order = cfg.get("SGorder", 2)
    try:
        if int(sg_frame) % 2 == 0:
            errors.append(f"SGframe must be odd (got {sg_frame})")
        if int(sg_frame) <= int(sg_order):
            errors.append(f"SGframe ({sg_frame}) must be > SGorder ({sg_order})")
    except (TypeError, ValueError):
        pass

    return errors


def load_config_file(config_file: str) -> tuple:
    """Load config JSON with defaults fallback.

    Returns:
        (cfg dict, list of warning strings)
    """
    cfg = default_config()
    warnings = []
    if config_file and os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                on_disk = json.load(f)
            if not isinstance(on_disk, dict):
                warnings.append("Config file does not contain a JSON object — using defaults.")
            else:
                defaults = default_config()
                unknown = [k for k in on_disk if k not in defaults]
                if unknown:
                    warnings.append(f"Unknown fields ignored: {unknown}")
                for k, default_val in defaults.items():
                    cfg[k] = on_disk.get(k, default_val)
                errors = validate_config(cfg)
                if errors:
                    warnings.extend(errors)
        except json.JSONDecodeError as e:
            warnings.append(f"Invalid JSON: {e} — using defaults.")
        except Exception as e:
            warnings.append(f"Failed to load config: {e} — using defaults.")
    return cfg, warnings


def save_config_file(config: dict, config_file: str):
    """Save config JSON to file."""
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def p_mean_process(data: np.ndarray, wl_corr: np.ndarray, wvn: np.ndarray, config: dict, skip_wl_correction: bool = False):
    """P-Mean pipeline using config parameters.

    Args:
        data: Raw spectrum data
        wl_corr: WL correction factor (ignored if skip_wl_correction=True)
        wvn: Wavenumber array
        config: Processing configuration
        skip_wl_correction: If True, skip spectral response correction (for Renishaw)
    """
    # 1) Baseline, response correction, cosmic ray removal
    spect = subtractBaseline(data)
    if not skip_wl_correction and wl_corr is not None:
        spect = SpectralResponseCorrection(wl_corr, spect)
    spect = CosmicRayRemoval(spect)

    # 2) Truncate
    start = float(config.get("Start", 900))
    stop = float(config.get("Stop", 1700))
    wvn_trunc, spect_trunc = Truncate(start, stop, wvn, spect)

    # 3) Binning - flatten arrays to ensure 1D input
    wvn_trunc = wvn_trunc.flatten()
    spect_trunc = spect_trunc.flatten()
    binwidth = float(config.get("BinWidth", 3.5))
    binned_spect, new_wvn = Binning(wvn_trunc[0], wvn_trunc[-1], wvn_trunc, spect_trunc, binwidth=binwidth)

    # 4) Fluorescence background subtraction
    polyorder = int(config.get("Polyorder", 7))
    fbs_maxiter = int(config.get("FBSMaxIter", 50))
    _, fbs_spect = FluorescenceBackgroundSubtraction(binned_spect, polyorder, max_iter=fbs_maxiter)

    # 5) Noise smoothing
    method = str(config.get("DenoiseMethod", "Savitzky-Golay"))
    if method == "Savitzky-Golay":
        SGorder = int(config.get("SGorder", 2))
        SGframe = int(config.get("SGframe", 7))
        finalSpect = Denoise(fbs_spect, SGorder=SGorder, SGframe=SGframe)
    elif method == "Moving Average":
        MAWindow = max(1, int(config.get("MAWindow", 5)))
        kernel = np.ones(MAWindow, dtype=np.float64) / MAWindow
        finalSpect = np.convolve(fbs_spect, kernel, mode='same')
    elif method == "Median Filter":
        from scipy.signal import medfilt
        MedianKernel = int(config.get("MedianKernel", 5))
        if MedianKernel % 2 == 0:
            MedianKernel += 1
        finalSpect = medfilt(fbs_spect, kernel_size=MedianKernel)
    else:
        finalSpect = fbs_spect

    # 6) Normalization
    norm_method = str(config.get("NormalizeMethod", "Mean")).lower()
    finalSpect = Normalize(finalSpect, method=norm_method)

    return new_wvn, finalSpect


class BatchWorker(QThread):
    """Worker thread for batch processing."""
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(list, int)  # processed_files, fail_count
    log = pyqtSignal(str, str)  # message, level (info/error/success)

    def __init__(self, data_files, wl_corr, wvn, config, output_folder, is_renishaw=False):
        super().__init__()
        self.data_files = data_files
        self.wl_corr = wl_corr
        self.wvn = wvn
        self.config = config
        self.output_folder = output_folder
        self.is_renishaw = is_renishaw
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        processed_files = []
        fail_count = 0

        # Build ops summary
        ops_kv = [
            f"Start{self.config['Start']}",
            f"Stop{self.config['Stop']}",
            f"P{self.config['Polyorder']}",
            f"DN{self.config['DenoiseMethod'].replace(' ', '')}",
            f"BW{self.config['BinWidth']}",
        ]
        if self.config["DenoiseMethod"] == "Savitzky-Golay":
            ops_kv += [f"SGO{self.config['SGorder']}", f"SGF{self.config['SGframe']}"]
        elif self.config["DenoiseMethod"] == "Moving Average":
            ops_kv += [f"MAW{self.config['MAWindow']}"]
        elif self.config["DenoiseMethod"] == "Median Filter":
            ops_kv += [f"MDK{self.config['MedianKernel']}"]
        ops_summary = "BatchPMean_" + "_".join(ops_kv)

        total = len(self.data_files)
        for i, path in enumerate(self.data_files):
            if self._is_cancelled:
                self.log.emit("Batch processing cancelled by user.", "error")
                break

            self.progress.emit(i + 1, total, os.path.basename(path))

            try:
                data_df = rdata.load_spectrum_data(path)
                if hasattr(data_df, "to_numpy"):
                    arr = data_df.to_numpy()
                else:
                    arr = np.asarray(data_df)
                arr = np.asarray(arr, dtype=np.float64)

                if self.is_renishaw:
                    # Renishaw: data file contains [wavenumber, intensity]
                    if arr.ndim == 2 and arr.shape[1] >= 2:
                        file_wvn = arr[:, 0].flatten()
                        raw_spec = arr[:, 1].flatten()
                    else:
                        raw_spec = arr.ravel()
                        file_wvn = self.wvn  # fallback to provided wvn
                    new_wvn, processed_spec = p_mean_process(
                        raw_spec, None, file_wvn, self.config, skip_wl_correction=True
                    )
                else:
                    # Non-Renishaw: single column intensity data
                    if arr.ndim == 2:
                        if arr.shape[1] == 1:
                            raw_spec = arr.ravel()
                        else:
                            raw_spec = arr.mean(axis=1)
                    else:
                        raw_spec = arr.ravel()
                    new_wvn, processed_spec = p_mean_process(
                        raw_spec, self.wl_corr, self.wvn, self.config, skip_wl_correction=False
                    )
                output_data = np.column_stack((new_wvn, processed_spec))

                prefix = os.path.basename(path)
                out_path = wdata.save_data(
                    output_data, prefix=prefix, operations=ops_summary,
                    base_dir=self.output_folder, file_ext="txt",
                    header="Wavenumber,SpectralIntensity"
                )
                processed_files.append(out_path)
                self.log.emit(f"[OK] {os.path.basename(path)} -> {os.path.basename(out_path)}", "success")

            except Exception as e:
                fail_count += 1
                err_type = type(e).__name__
                self.log.emit(
                    f"[ERR] {os.path.basename(path)}: {err_type}: {e} (output: {self.output_folder})",
                    "error"
                )

        self.finished.emit(processed_files, fail_count)


class PreviewCanvas(FigureCanvas):
    """Canvas for preview plot with dark theme. Font sizes adapt to canvas size."""

    def __init__(self, parent=None, width=6, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor(Colors.BG_SECONDARY)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(200, 150)
        self._style_axis()
        self.draw()

    def sizeHint(self):
        return QSize(400, 300)

    def minimumSizeHint(self):
        return QSize(200, 150)

    def _font_sizes(self):
        w = self.width()
        title = max(9, min(16, int(w / 40)))
        label = max(8, min(13, int(w / 50)))
        tick = max(7, min(12, int(w / 55)))
        legend = max(7, min(11, int(w / 55)))
        return title, label, tick, legend

    def _style_axis(self):
        fs_title, _, fs_tick, _ = self._font_sizes()
        self.ax.set_facecolor(Colors.BG_TERTIARY)
        self.ax.grid(True, alpha=0.2, linestyle='--', color=Colors.BORDER)
        self.ax.tick_params(labelsize=fs_tick, colors=Colors.TEXT_SECONDARY)
        for spine in self.ax.spines.values():
            spine.set_color(Colors.BORDER)
        self.ax.set_title("Preview", fontsize=fs_title, fontweight='bold', color=Colors.TEXT_PRIMARY)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        fs_title, fs_label, fs_tick, fs_legend = self._font_sizes()
        self.ax.title.set_fontsize(fs_title)
        self.ax.xaxis.label.set_fontsize(fs_label)
        self.ax.yaxis.label.set_fontsize(fs_label)
        self.ax.tick_params(labelsize=fs_tick)
        legend = self.ax.get_legend()
        if legend:
            for text in legend.get_texts():
                text.set_fontsize(fs_legend)
        self.fig.tight_layout(pad=2.0)
        self.draw_idle()

    def plot_preview(self, wvn_before, spect_before, wvn_after, spect_after, filename=""):
        fs_title, fs_label, _, fs_legend = self._font_sizes()
        self.ax.clear()
        self._style_axis()

        if wvn_before is not None and len(wvn_before) == len(spect_before):
            self.ax.plot(wvn_before, spect_before, color=Colors.TEXT_TERTIARY, linewidth=1.2, alpha=0.6, label='Raw')
        else:
            self.ax.plot(spect_before, color=Colors.TEXT_TERTIARY, linewidth=1.2, alpha=0.6, label='Raw')

        if wvn_after is not None and len(wvn_after) == len(spect_after):
            self.ax.plot(wvn_after, spect_after, color=Colors.SUCCESS, linewidth=1.5, label='Processed')
        else:
            self.ax.plot(spect_after, color=Colors.SUCCESS, linewidth=1.5, label='Processed')

        self.ax.set_xlabel("Wavenumber (cm$^{-1}$)", fontsize=fs_label, color=Colors.TEXT_SECONDARY)
        self.ax.set_ylabel("Intensity", fontsize=fs_label, color=Colors.TEXT_SECONDARY)
        self.ax.set_title(f"Preview: {filename}", fontsize=fs_title, fontweight='bold', color=Colors.TEXT_PRIMARY)
        self.ax.legend(loc='best', fontsize=fs_legend, facecolor=Colors.BG_TERTIARY, edgecolor=Colors.BORDER, labelcolor=Colors.TEXT_PRIMARY)
        self.fig.tight_layout(pad=2.0)
        self.draw()

    def clear_plot(self):
        self.ax.clear()
        self._style_axis()
        self.draw()


class BatchPMeanUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Batch P_Mean Processing - Enhanced")
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1200, int(screen.width() * 0.9)), min(800, int(screen.height() * 0.9)))
        self.move(screen.center() - self.rect().center())

        # Get current system from config
        self.config_manager = ConfigManager()
        self.current_system = self.config_manager.params.get("System", "")
        # Apply unified dark theme
        self.setStyleSheet(get_stylesheet())

        # State
        self.data_files = []
        self.wlcorr_file = None
        self.wvn_file = None
        self.output_root = None
        self.config_path = "p_mean_config.json"
        self.config, _ = load_config_file(self.config_path)
        self.config_modified = False
        self.worker = None

        # Cached data for preview
        self.cached_wl_corr = None
        self.cached_wvn = None

        self._build_ui()
        self._update_denoise_visibility()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Use QSplitter so user can drag to resize panels
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left panel - Parameters & Files (scrollable)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(250)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Parameters Group
        params_group = QGroupBox("Processing Parameters")
        params_form = QFormLayout(params_group)
        params_form.setSpacing(8)
        params_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.edit_start = QLineEdit(str(self.config["Start"]))
        self.edit_start.setMinimumHeight(32)
        self.edit_stop = QLineEdit(str(self.config["Stop"]))
        self.edit_stop.setMinimumHeight(32)
        self.edit_binw = QLineEdit(str(self.config["BinWidth"]))
        self.edit_binw.setMinimumHeight(32)
        self.edit_poly = QLineEdit(str(self.config["Polyorder"]))
        self.edit_poly.setMinimumHeight(32)
        self.edit_fbs_maxiter = QLineEdit(str(self.config["FBSMaxIter"]))
        self.edit_fbs_maxiter.setMinimumHeight(32)
        self.combo_norm = QComboBox()
        self.combo_norm.addItems(["Mean", "Max", "Area"])
        self.combo_norm.setCurrentText(self.config.get("NormalizeMethod", "Mean"))
        self.combo_norm.setMinimumHeight(32)

        for w in [self.edit_start, self.edit_stop,
                  self.edit_binw, self.edit_poly, self.edit_fbs_maxiter]:
            w.textChanged.connect(self._mark_config_modified)
        self.combo_norm.currentIndexChanged.connect(self._mark_config_modified)

        params_form.addRow("Start (cm⁻¹):", self.edit_start)
        params_form.addRow("Stop (cm⁻¹):", self.edit_stop)
        params_form.addRow("BinWidth:", self.edit_binw)
        params_form.addRow("Polyorder:", self.edit_poly)
        params_form.addRow("FBS Max Iterations:", self.edit_fbs_maxiter)
        params_form.addRow("Normalize Method:", self.combo_norm)

        # Noise smoothing settings
        self.combo_denoise = QComboBox()
        self.combo_denoise.addItems(["Savitzky-Golay", "Moving Average", "Median Filter", "None"])
        self.combo_denoise.setCurrentText(self.config.get("DenoiseMethod", "Savitzky-Golay"))
        self.combo_denoise.currentIndexChanged.connect(self._update_denoise_visibility)
        self.combo_denoise.currentIndexChanged.connect(self._mark_config_modified)
        self.combo_denoise.setMinimumHeight(32)
        params_form.addRow("Noise Smoothing Method:", self.combo_denoise)

        self.edit_sgorder = QLineEdit(str(self.config["SGorder"]))
        self.edit_sgorder.setMinimumHeight(32)
        self.edit_sgframe = QLineEdit(str(self.config["SGframe"]))
        self.edit_sgframe.setMinimumHeight(32)
        self.edit_mawin = QLineEdit(str(self.config["MAWindow"]))
        self.edit_mawin.setMinimumHeight(32)
        self.edit_medk = QLineEdit(str(self.config["MedianKernel"]))
        self.edit_medk.setMinimumHeight(32)

        self.lbl_sgorder = QLabel("SG Order:")
        self.lbl_sgframe = QLabel("SG Frame:")
        self.lbl_mawin = QLabel("MA Window:")
        self.lbl_medk = QLabel("Median Kernel:")

        params_form.addRow(self.lbl_sgorder, self.edit_sgorder)
        params_form.addRow(self.lbl_sgframe, self.edit_sgframe)
        params_form.addRow(self.lbl_mawin, self.edit_mawin)
        params_form.addRow(self.lbl_medk, self.edit_medk)

        # Config buttons
        cfg_btns = QHBoxLayout()
        cfg_btns.setSpacing(6)
        btn_load_cfg = QPushButton("Load")
        btn_load_cfg.clicked.connect(self.on_load_config)
        btn_load_cfg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_save_cfg = QPushButton("Save")
        btn_save_cfg.clicked.connect(self.on_save_config)
        btn_save_cfg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_reset_cfg = QPushButton("Reset")
        btn_reset_cfg.clicked.connect(self.on_reset_config)
        btn_reset_cfg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cfg_btns.addWidget(btn_load_cfg)
        cfg_btns.addWidget(btn_save_cfg)
        cfg_btns.addWidget(btn_reset_cfg)
        params_form.addRow(cfg_btns)

        left_layout.addWidget(params_group)

        # Files Group
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
            f"color: {Colors.SUCCESS}; font-weight: bold; padding: 10px; "
            f"background-color: {Colors.SUCCESS_BG}; border-radius: 8px; font-size: {Fonts.SIZE_BASE}px;"
            if is_renishaw else
            f"color: {Colors.PRIMARY}; font-weight: bold; padding: 10px; "
            f"background-color: {Colors.PRIMARY_MUTED}; border-radius: 8px; font-size: {Fonts.SIZE_BASE}px;"
        )
        files_layout.addWidget(self.lbl_system_info)

        # Data files
        btn_select_data = QPushButton("Select Data Files (Raw Spectrum)")
        btn_select_data.clicked.connect(self.on_select_data)
        btn_select_data.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        files_layout.addWidget(btn_select_data)

        self.list_data = QListWidget()
        self.list_data.setMaximumHeight(100)
        files_layout.addWidget(self.list_data)

        self.lbl_data_count = QLabel("0 files selected")
        self.lbl_data_count.setStyleSheet("color: #6c757d; font-style: italic;")
        files_layout.addWidget(self.lbl_data_count)

        # WL Correction (container widget for visibility control)
        self.wl_widget = QWidget()
        wl_layout = QHBoxLayout(self.wl_widget)
        wl_layout.setContentsMargins(0, 0, 0, 0)
        wl_layout.setSpacing(8)
        self.btn_select_wlcorr = QPushButton("Select WL Correction")
        self.btn_select_wlcorr.clicked.connect(self.on_select_wlcorr)
        self.btn_select_wlcorr.setMinimumWidth(160)
        wl_layout.addWidget(self.btn_select_wlcorr)
        self.lbl_wlcorr = QLabel("Not selected")
        self.lbl_wlcorr.setStyleSheet("color: #dc3545;")
        self.lbl_wlcorr.setWordWrap(True)
        wl_layout.addWidget(self.lbl_wlcorr, 1)
        files_layout.addWidget(self.wl_widget)

        # Calibration (container widget for visibility control)
        self.cal_widget = QWidget()
        cal_layout = QHBoxLayout(self.cal_widget)
        cal_layout.setContentsMargins(0, 0, 0, 0)
        cal_layout.setSpacing(8)
        self.btn_select_wvn = QPushButton("Select Calibration (.mat)")
        self.btn_select_wvn.clicked.connect(self.on_select_wvn)
        self.btn_select_wvn.setMinimumWidth(160)
        cal_layout.addWidget(self.btn_select_wvn)
        self.lbl_wvn = QLabel("Not selected")
        self.lbl_wvn.setStyleSheet("color: #dc3545;")
        self.lbl_wvn.setWordWrap(True)
        cal_layout.addWidget(self.lbl_wvn, 1)
        files_layout.addWidget(self.cal_widget)

        # Hide WL/Cal widgets for Renishaw
        self.wl_widget.setVisible(not is_renishaw)
        self.cal_widget.setVisible(not is_renishaw)

        # Output folder
        out_layout = QHBoxLayout()
        out_layout.setSpacing(8)
        btn_select_output = QPushButton("Output Folder")
        btn_select_output.clicked.connect(self.on_select_output)
        btn_select_output.setMinimumWidth(120)
        out_layout.addWidget(btn_select_output)
        self.edit_output = QLineEdit()
        self.edit_output.setReadOnly(True)
        self.edit_output.setPlaceholderText("Auto: ./Processed")
        self.edit_output.setMinimumHeight(32)
        out_layout.addWidget(self.edit_output, 1)
        files_layout.addLayout(out_layout)

        # Optional subfolder
        sub_layout = QHBoxLayout()
        sub_layout.setSpacing(8)
        lbl_sub = QLabel("Subfolder")
        lbl_sub.setMinimumWidth(120)
        sub_layout.addWidget(lbl_sub)
        self.edit_subfolder = QLineEdit()
        self.edit_subfolder.setPlaceholderText("Optional (e.g. Run_01)")
        self.edit_subfolder.setMinimumHeight(32)
        sub_layout.addWidget(self.edit_subfolder, 1)
        files_layout.addLayout(sub_layout)

        left_layout.addWidget(files_group)

        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(8)

        self.btn_preview = QPushButton("Preview First File")
        self.btn_preview.setProperty("class", "info")
        self.btn_preview.clicked.connect(self.on_preview)
        self.btn_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        actions_layout.addWidget(self.btn_preview)

        self.btn_start = QPushButton("Start Batch Process")
        self.btn_start.setProperty("class", "success")
        self.btn_start.clicked.connect(self.on_start_batch)
        self.btn_start.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        actions_layout.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setProperty("class", "danger")
        self.btn_cancel.clicked.connect(self.on_cancel)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        actions_layout.addWidget(self.btn_cancel)

        left_layout.addWidget(actions_group)

        # Progress
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.lbl_progress = QLabel("Ready")
        self.lbl_progress.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.lbl_progress)

        left_layout.addWidget(progress_group)
        left_layout.addStretch()

        # Right panel - Preview & Log
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_canvas = PreviewCanvas(self, width=6, height=4, dpi=100)
        preview_layout.addWidget(self.preview_canvas)
        right_layout.addWidget(preview_group)

        # Log
        log_group = QGroupBox("Processing Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        log_layout.addWidget(self.log_text)

        log_btns = QHBoxLayout()
        log_btns.setSpacing(8)
        btn_clear_log = QPushButton("Clear Log")
        btn_clear_log.clicked.connect(self.log_text.clear)
        btn_clear_log.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_export_log = QPushButton("Export Log")
        btn_export_log.clicked.connect(self.on_export_log)
        btn_export_log.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        log_btns.addWidget(btn_clear_log)
        log_btns.addWidget(btn_export_log)
        log_btns.addStretch()
        log_layout.addLayout(log_btns)

        right_layout.addWidget(log_group)

        # Add to splitter
        left_scroll.setWidget(left_panel)
        splitter.addWidget(left_scroll)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 620])
        main_layout.addWidget(splitter)

    def _is_renishaw_system(self):
        """Check if current system is Renishaw."""
        return self.current_system.lower() == "renishaw"

    def _mark_config_modified(self):
        self.config_modified = True

    def _update_denoise_visibility(self):
        method = self.combo_denoise.currentText()
        is_sg = method == "Savitzky-Golay"
        is_ma = method == "Moving Average"
        is_md = method == "Median Filter"

        self.lbl_sgorder.setVisible(is_sg)
        self.edit_sgorder.setVisible(is_sg)
        self.lbl_sgframe.setVisible(is_sg)
        self.edit_sgframe.setVisible(is_sg)
        self.lbl_mawin.setVisible(is_ma)
        self.edit_mawin.setVisible(is_ma)
        self.lbl_medk.setVisible(is_md)
        self.edit_medk.setVisible(is_md)

    def _gather_config(self) -> dict:
        """Gather config from UI with validation."""
        cfg = {
            "Start": float(self.edit_start.text()),
            "Stop": float(self.edit_stop.text()),
            "BinWidth": float(self.edit_binw.text()),
            "Polyorder": int(self.edit_poly.text()),
            "FBSMaxIter": int(self.edit_fbs_maxiter.text()),
            "NormalizeMethod": self.combo_norm.currentText(),
            "DenoiseMethod": self.combo_denoise.currentText(),
            "SGorder": int(self.edit_sgorder.text()),
            "SGframe": int(self.edit_sgframe.text()),
            "MAWindow": int(self.edit_mawin.text()),
            "MedianKernel": int(self.edit_medk.text()),
        }

        if cfg["Stop"] <= cfg["Start"]:
            raise ValueError("Stop must be > Start")
        if cfg["BinWidth"] <= 0:
            raise ValueError("BinWidth must be > 0")
        if cfg["DenoiseMethod"] == "Savitzky-Golay":
            if cfg["SGframe"] < 3 or cfg["SGframe"] % 2 == 0:
                raise ValueError("SGframe must be odd >= 3")

        return cfg

    def _apply_config(self, cfg: dict):
        """Apply config to UI."""
        self.edit_start.setText(str(cfg.get("Start", 900)))
        self.edit_stop.setText(str(cfg.get("Stop", 1700)))
        self.edit_binw.setText(str(cfg.get("BinWidth", 3.5)))
        self.edit_poly.setText(str(cfg.get("Polyorder", 7)))
        self.edit_fbs_maxiter.setText(str(cfg.get("FBSMaxIter", 50)))
        self.combo_norm.setCurrentText(cfg.get("NormalizeMethod", "Mean"))
        self.combo_denoise.setCurrentText(cfg.get("DenoiseMethod", "Savitzky-Golay"))
        self.edit_sgorder.setText(str(cfg.get("SGorder", 2)))
        self.edit_sgframe.setText(str(cfg.get("SGframe", 7)))
        self.edit_mawin.setText(str(cfg.get("MAWindow", 5)))
        self.edit_medk.setText(str(cfg.get("MedianKernel", 5)))
        self._update_denoise_visibility()
        self.config_modified = False

    def _log(self, message: str, level: str = "info"):
        """Add message to log with color coding."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {"info": "#333", "success": "#28a745", "error": "#dc3545", "warning": "#ffc107"}
        color = colors.get(level, "#333")
        html = f'<span style="color: #6c757d;">[{timestamp}]</span> <span style="color: {color};">{message}</span>'
        self.log_text.append(html)
        self.log_text.moveCursor(QTextCursor.End)

    def _load_support_files(self) -> bool:
        """Load WL correction and calibration files into cache.
        For Renishaw systems, these are not required."""
        is_renishaw = self._is_renishaw_system()

        if is_renishaw:
            # Renishaw doesn't need WL correction or calibration files
            self.cached_wl_corr = None
            self.cached_wvn = None
            return True

        # Non-Renishaw: require both files
        if not self.wlcorr_file or not self.wvn_file:
            return False

        try:
            # Load WL correction - keep 2D structure for SpectralResponseCorrection
            wl_corr_df = rdata.read_txt_file(self.wlcorr_file)
            if wl_corr_df is None:
                raise ValueError("WL correction read failed")
            if hasattr(wl_corr_df, "to_numpy"):
                self.cached_wl_corr = wl_corr_df.to_numpy().astype(np.float64)
            else:
                self.cached_wl_corr = np.asarray(wl_corr_df, dtype=np.float64)

            self.cached_wvn = rdata.getwvnfrompath(self.wvn_file).flatten().astype(np.float64)
            return True

        except Exception as e:
            self._log(f"Failed to load support files: {e}", "error")
            return False

    # Slots
    def on_load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Config", "", "JSON Files (*.json)")
        if path:
            cfg, warnings = load_config_file(path)
            if warnings:
                self._log("Config warnings:", "warning")
                for w in warnings:
                    self._log(f"  • {w}", "warning")
            self.config = cfg
            self._apply_config(self.config)
            self.config_path = path
            self._log(f"Config loaded: {path}", "info")

    def on_save_config(self):
        try:
            cfg = self._gather_config()
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save Config", self.config_path, "JSON Files (*.json)")
        if path:
            try:
                save_config_file(cfg, path)
                self.config_path = path
                self.config = cfg
                self.config_modified = False
                self._log(f"Config saved: {path}", "success")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save: {e}")

    def on_reset_config(self):
        self.config = default_config()
        self._apply_config(self.config)
        self._log("Config reset to defaults", "info")

    def on_select_data(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Data Files", "",
            "Text Files (*.txt *.csv);;All Files (*)"
        )
        if files:
            self.data_files = files
            self.list_data.clear()
            for f in files:
                self.list_data.addItem(os.path.basename(f))
            self.lbl_data_count.setText(f"{len(files)} files selected")
            self._log(f"Selected {len(files)} data files", "info")

    def on_select_wlcorr(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Select WL Correction", "",
            "Text/CSV Files (*.txt *.csv);;All Files (*)"
        )
        if file:
            self.wlcorr_file = file
            self.lbl_wlcorr.setText(os.path.basename(file))
            self.lbl_wlcorr.setStyleSheet("color: #28a745;")
            self.cached_wl_corr = None  # Clear cache
            self._log(f"WL Correction: {os.path.basename(file)}", "info")

    def on_select_wvn(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Select Calibration", "",
            "MAT Files (*.mat);;All Files (*)"
        )
        if file:
            self.wvn_file = file
            self.lbl_wvn.setText(os.path.basename(file))
            self.lbl_wvn.setStyleSheet("color: #28a745;")
            self.cached_wvn = None  # Clear cache
            self._log(f"Calibration: {os.path.basename(file)}", "info")

    def on_select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_root = folder
            self.edit_output.setText(folder)
            self._log(f"Output folder: {folder}", "info")

    def on_preview(self):
        """Preview processing on first file."""
        is_renishaw = self._is_renishaw_system()

        if not self.data_files:
            QMessageBox.warning(self, "Error", "No data files selected")
            return

        # For non-Renishaw, require WL correction and calibration files
        if not is_renishaw and (not self.wlcorr_file or not self.wvn_file):
            QMessageBox.warning(self, "Error", "WL Correction and Calibration files required")
            return

        try:
            cfg = self._gather_config()
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
            return

        if not self._load_support_files():
            return

        try:
            path = self.data_files[0]
            data_df = rdata.load_spectrum_data(path)
            if hasattr(data_df, "to_numpy"):
                arr = data_df.to_numpy()
            else:
                arr = np.asarray(data_df)
            arr = np.asarray(arr, dtype=np.float64)

            if is_renishaw:
                # Renishaw: data contains [wavenumber, intensity]
                if arr.ndim == 2 and arr.shape[1] >= 2:
                    file_wvn = arr[:, 0].flatten()
                    raw_spec = arr[:, 1].flatten()
                else:
                    raw_spec = arr.ravel()
                    file_wvn = np.arange(len(raw_spec), dtype=np.float64)
                new_wvn, processed_spec = p_mean_process(
                    raw_spec, None, file_wvn, cfg, skip_wl_correction=True
                )
                wvn_for_plot = file_wvn
            else:
                # Non-Renishaw: single column intensity
                if arr.ndim == 2:
                    raw_spec = arr.ravel() if arr.shape[1] == 1 else arr.mean(axis=1)
                else:
                    raw_spec = arr.ravel()
                new_wvn, processed_spec = p_mean_process(
                    raw_spec, self.cached_wl_corr, self.cached_wvn, cfg, skip_wl_correction=False
                )
                wvn_for_plot = self.cached_wvn

            self.preview_canvas.plot_preview(
                wvn_for_plot, raw_spec,
                new_wvn, processed_spec,
                os.path.basename(path)
            )
            self._log(f"Preview generated for: {os.path.basename(path)}", "success")

        except Exception as e:
            self._log(f"Preview failed: {e}", "error")
            QMessageBox.warning(self, "Error", f"Preview failed: {e}")

    def on_start_batch(self):
        """Start batch processing."""
        is_renishaw = self._is_renishaw_system()

        if not self.data_files:
            QMessageBox.warning(self, "Error", "No data files selected")
            return

        # For non-Renishaw, require WL correction and calibration files
        if not is_renishaw and (not self.wlcorr_file or not self.wvn_file):
            QMessageBox.warning(self, "Error", "WL Correction and Calibration files required")
            return

        try:
            cfg = self._gather_config()
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
            return

        if not self._load_support_files():
            return

        # Output folder
        if self.output_root:
            output_folder = self.output_root
        else:
            output_folder = os.path.join(os.path.dirname(self.data_files[0]), "Processed")
        subfolder = self.edit_subfolder.text().strip()
        if subfolder:
            output_folder = os.path.join(output_folder, subfolder)
        try:
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            err_type = type(e).__name__
            self._log(f"Failed to create output folder '{output_folder}': {err_type}: {e}", "error")
            QMessageBox.warning(self, "Error", f"Failed to create output folder:\n{output_folder}\n\n{err_type}: {e}")
            return

        # Disable controls
        self.btn_start.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(self.data_files))

        system_info = " (Renishaw mode - no WL correction)" if is_renishaw else ""
        self._log(f"Starting batch processing: {len(self.data_files)} files{system_info}", "info")

        # Start worker
        self.worker = BatchWorker(
            self.data_files, self.cached_wl_corr, self.cached_wvn,
            cfg, output_folder, is_renishaw=is_renishaw
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._log)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def on_cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()

    def _on_progress(self, current, total, filename):
        self.progress_bar.setValue(current)
        self.lbl_progress.setText(f"Processing {current}/{total}: {filename}")

    def _on_finished(self, processed_files, fail_count):
        self.btn_start.setEnabled(True)
        self.btn_preview.setEnabled(True)
        self.btn_cancel.setEnabled(False)

        success_count = len(processed_files)
        self.lbl_progress.setText(f"Done: {success_count} success, {fail_count} failed")
        self.progress_bar.setValue(self.progress_bar.maximum())

        self._log(f"Batch complete: {success_count} success, {fail_count} failed", "success" if fail_count == 0 else "warning")

        msg = f"Batch processing complete.\n\nSuccess: {success_count}\nFailed: {fail_count}"
        if processed_files:
            msg += f"\n\nOutput folder:\n{os.path.dirname(processed_files[0])}"
        QMessageBox.information(self, "Complete", msg)

    def on_export_log(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Log", "batch_log.txt", "Text Files (*.txt)"
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(self.log_text.toPlainText())
                self._log(f"Log exported: {filepath}", "success")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to export: {e}")

    def closeEvent(self, event):
        """Handle window close - prompt to save config if modified."""
        if self.config_modified:
            reply = QMessageBox.question(
                self, "Save Configuration?",
                "Configuration has been modified. Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            if reply == QMessageBox.Save:
                self.on_save_config()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = BatchPMeanUI()
    win.show()
    sys.exit(app.exec_())
