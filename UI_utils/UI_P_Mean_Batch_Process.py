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
    QSplitter, QSizePolicy, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.io import wdata, rdata
from utils.SpectralPreprocess import (
    Binning, Denoise, Truncate, CosmicRayRemoval,
    SpectralResponseCorrection, subtractBaseline,
    FluorescenceBackgroundSubtraction
)


def default_config() -> dict:
    """Return default configuration."""
    return {
        "Start": 900,
        "Stop": 1700,
        "Polyorder": 7,
        "DenoiseMethod": "Savitzky-Golay",
        "BinWidth": 3.5,
        "SGorder": 2,
        "SGframe": 7,
        "MAWindow": 5,
        "MedianKernel": 5
    }


def load_config_file(config_file: str) -> dict:
    """Load config JSON with defaults fallback."""
    cfg = default_config()
    if config_file and os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                on_disk = json.load(f)
            for k, v in default_config().items():
                cfg[k] = on_disk.get(k, v)
        except Exception as e:
            print(f"[WARN] Failed to load config: {e}")
    return cfg


def save_config_file(config: dict, config_file: str):
    """Save config JSON to file."""
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def p_mean_process(data: np.ndarray, wl_corr: np.ndarray, wvn: np.ndarray, config: dict):
    """P-Mean pipeline using config parameters."""
    # 1) Baseline, response correction, cosmic ray removal
    spect = subtractBaseline(data)
    spect = SpectralResponseCorrection(wl_corr, spect)
    spect = CosmicRayRemoval(spect)

    # 2) Truncate
    start = float(config.get("Start", 900))
    stop = float(config.get("Stop", 1700))
    wvn_trunc, spect_trunc = Truncate(start, stop, wvn, spect)

    # 3) Binning
    binwidth = float(config.get("BinWidth", 3.5))
    binned_spect, new_wvn = Binning(wvn_trunc[0], wvn_trunc[-1], wvn_trunc, spect_trunc, binwidth=binwidth)

    # 4) Denoise
    method = str(config.get("DenoiseMethod", "Savitzky-Golay"))
    if method == "Savitzky-Golay":
        SGorder = int(config.get("SGorder", 2))
        SGframe = int(config.get("SGframe", 7))
        processed_spect = Denoise(binned_spect, SGorder=SGorder, SGframe=SGframe)
    elif method == "Moving Average":
        MAWindow = max(1, int(config.get("MAWindow", 5)))
        kernel = np.ones(MAWindow, dtype=np.float64) / MAWindow
        processed_spect = np.convolve(binned_spect, kernel, mode='same')
    elif method == "Median Filter":
        from scipy.signal import medfilt
        MedianKernel = int(config.get("MedianKernel", 5))
        if MedianKernel % 2 == 0:
            MedianKernel += 1
        processed_spect = medfilt(binned_spect, kernel_size=MedianKernel)
    else:
        processed_spect = binned_spect

    # 5) Fluorescence background subtraction
    polyorder = int(config.get("Polyorder", 7))
    _, finalSpect = FluorescenceBackgroundSubtraction(processed_spect, polyorder)

    return new_wvn, finalSpect


class BatchWorker(QThread):
    """Worker thread for batch processing."""
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(list, int)  # processed_files, fail_count
    log = pyqtSignal(str, str)  # message, level (info/error/success)

    def __init__(self, data_files, wl_corr, wvn, config, output_folder):
        super().__init__()
        self.data_files = data_files
        self.wl_corr = wl_corr
        self.wvn = wvn
        self.config = config
        self.output_folder = output_folder
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

                if arr.ndim == 2:
                    if arr.shape[1] == 1:
                        raw_spec = arr.ravel()
                    else:
                        raw_spec = arr.mean(axis=1)
                else:
                    raw_spec = arr.ravel()

                new_wvn, processed_spec = p_mean_process(raw_spec, self.wl_corr, self.wvn, self.config)
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
                self.log.emit(f"[ERR] {os.path.basename(path)}: {str(e)}", "error")

        self.finished.emit(processed_files, fail_count)


class PreviewCanvas(FigureCanvas):
    """Canvas for preview plot."""

    def __init__(self, parent=None, width=6, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor('#f8f9fa')
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._style_axis()

    def _style_axis(self):
        self.ax.set_facecolor('#ffffff')
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.set_title("Preview", fontsize=11, fontweight='bold')

    def plot_preview(self, wvn_before, spect_before, wvn_after, spect_after, filename=""):
        self.ax.clear()

        if wvn_before is not None and len(wvn_before) == len(spect_before):
            self.ax.plot(wvn_before, spect_before, 'b-', linewidth=1, alpha=0.5, label='Raw')
        else:
            self.ax.plot(spect_before, 'b-', linewidth=1, alpha=0.5, label='Raw')

        if wvn_after is not None and len(wvn_after) == len(spect_after):
            self.ax.plot(wvn_after, spect_after, 'r-', linewidth=1.2, label='Processed')
        else:
            self.ax.plot(spect_after, 'r-', linewidth=1.2, label='Processed')

        self.ax.set_xlabel("Wavenumber (cm$^{-1}$)", fontsize=10)
        self.ax.set_ylabel("Intensity", fontsize=10)
        self.ax.set_title(f"Preview: {filename}", fontsize=11, fontweight='bold')
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.legend(loc='best', fontsize=9)
        self.fig.tight_layout()
        self.draw()

    def clear_plot(self):
        self.ax.clear()
        self._style_axis()
        self.draw()


class BatchPMeanUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Batch P_Mean Processing - Enhanced")
        self.setGeometry(100, 100, 1200, 800)
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
            QPushButton:pressed { background-color: #e8eaed; }
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
            QPushButton[class="primary"]:hover { background-color: #1557b0; }
            QPushButton[class="success"] {
                background-color: #1e8e3e;
                color: white;
                border: none;
                font-weight: 600;
            }
            QPushButton[class="success"]:hover { background-color: #137333; }
            QPushButton[class="info"] {
                background-color: #1a73e8;
                color: white;
                border: none;
            }
            QPushButton[class="info"]:hover { background-color: #1557b0; }
            QPushButton[class="danger"] {
                background-color: #d93025;
                color: white;
                border: none;
            }
            QPushButton[class="danger"]:hover { background-color: #b31412; }
            QLineEdit {
                padding: 8px 10px;
                border: 2px solid #dadce0;
                border-radius: 6px;
                background-color: #ffffff;
                font-size: 13px;
                color: #202124;
            }
            QLineEdit:focus { border-color: #1a73e8; }
            QComboBox {
                padding: 8px 10px;
                border: 2px solid #dadce0;
                border-radius: 6px;
                background-color: #ffffff;
                font-size: 13px;
                color: #202124;
            }
            QComboBox:focus { border-color: #1a73e8; }
            QTextEdit {
                border: 2px solid #dadce0;
                border-radius: 6px;
                background-color: #ffffff;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                padding: 8px;
            }
            QProgressBar {
                border: 2px solid #dadce0;
                border-radius: 6px;
                text-align: center;
                background-color: #f1f3f4;
                font-weight: 500;
            }
            QProgressBar::chunk {
                background-color: #1e8e3e;
                border-radius: 4px;
            }
            QListWidget {
                border: 2px solid #dadce0;
                border-radius: 6px;
                background-color: #ffffff;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #e8f0fe;
                color: #1a73e8;
            }
            QLabel { color: #3c4043; }
        """)

        # State
        self.data_files = []
        self.wlcorr_file = None
        self.wvn_file = None
        self.output_root = None
        self.config_path = "p_mean_config.json"
        self.config = load_config_file(self.config_path)
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

        # Left panel - Parameters & Files
        left_panel = QWidget()
        left_panel.setFixedWidth(420)
        left_layout = QVBoxLayout(left_panel)

        # Parameters Group
        params_group = QGroupBox("Processing Parameters")
        params_form = QFormLayout(params_group)

        self.edit_start = QLineEdit(str(self.config["Start"]))
        self.edit_stop = QLineEdit(str(self.config["Stop"]))
        self.edit_poly = QLineEdit(str(self.config["Polyorder"]))
        self.edit_binw = QLineEdit(str(self.config["BinWidth"]))

        self.edit_start.textChanged.connect(self._mark_config_modified)
        self.edit_stop.textChanged.connect(self._mark_config_modified)
        self.edit_poly.textChanged.connect(self._mark_config_modified)
        self.edit_binw.textChanged.connect(self._mark_config_modified)

        params_form.addRow("Start (cm⁻¹):", self.edit_start)
        params_form.addRow("Stop (cm⁻¹):", self.edit_stop)
        params_form.addRow("Polyorder:", self.edit_poly)
        params_form.addRow("BinWidth:", self.edit_binw)

        # Denoise settings
        self.combo_denoise = QComboBox()
        self.combo_denoise.addItems(["Savitzky-Golay", "Moving Average", "Median Filter", "None"])
        self.combo_denoise.setCurrentText(self.config.get("DenoiseMethod", "Savitzky-Golay"))
        self.combo_denoise.currentIndexChanged.connect(self._update_denoise_visibility)
        self.combo_denoise.currentIndexChanged.connect(self._mark_config_modified)
        params_form.addRow("Denoise Method:", self.combo_denoise)

        self.edit_sgorder = QLineEdit(str(self.config["SGorder"]))
        self.edit_sgframe = QLineEdit(str(self.config["SGframe"]))
        self.edit_mawin = QLineEdit(str(self.config["MAWindow"]))
        self.edit_medk = QLineEdit(str(self.config["MedianKernel"]))

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
        btn_load_cfg = QPushButton("Load Config")
        btn_load_cfg.clicked.connect(self.on_load_config)
        btn_save_cfg = QPushButton("Save Config")
        btn_save_cfg.clicked.connect(self.on_save_config)
        btn_reset_cfg = QPushButton("Reset Default")
        btn_reset_cfg.clicked.connect(self.on_reset_config)
        cfg_btns.addWidget(btn_load_cfg)
        cfg_btns.addWidget(btn_save_cfg)
        cfg_btns.addWidget(btn_reset_cfg)
        params_form.addRow(cfg_btns)

        left_layout.addWidget(params_group)

        # Files Group
        files_group = QGroupBox("Input Files")
        files_layout = QVBoxLayout(files_group)

        # Data files
        btn_select_data = QPushButton("Select Data Files (Raw Spectrum)")
        btn_select_data.clicked.connect(self.on_select_data)
        files_layout.addWidget(btn_select_data)

        self.list_data = QListWidget()
        self.list_data.setMaximumHeight(100)
        files_layout.addWidget(self.list_data)

        self.lbl_data_count = QLabel("0 files selected")
        self.lbl_data_count.setStyleSheet("color: #6c757d; font-style: italic;")
        files_layout.addWidget(self.lbl_data_count)

        # WL Correction
        wl_layout = QHBoxLayout()
        btn_select_wlcorr = QPushButton("Select WL Correction")
        btn_select_wlcorr.clicked.connect(self.on_select_wlcorr)
        wl_layout.addWidget(btn_select_wlcorr)
        self.lbl_wlcorr = QLabel("Not selected")
        self.lbl_wlcorr.setStyleSheet("color: #dc3545;")
        wl_layout.addWidget(self.lbl_wlcorr, 1)
        files_layout.addLayout(wl_layout)

        # Calibration
        cal_layout = QHBoxLayout()
        btn_select_wvn = QPushButton("Select Calibration (.mat)")
        btn_select_wvn.clicked.connect(self.on_select_wvn)
        cal_layout.addWidget(btn_select_wvn)
        self.lbl_wvn = QLabel("Not selected")
        self.lbl_wvn.setStyleSheet("color: #dc3545;")
        cal_layout.addWidget(self.lbl_wvn, 1)
        files_layout.addLayout(cal_layout)

        # Output folder
        out_layout = QHBoxLayout()
        btn_select_output = QPushButton("Output Folder")
        btn_select_output.clicked.connect(self.on_select_output)
        out_layout.addWidget(btn_select_output)
        self.edit_output = QLineEdit()
        self.edit_output.setReadOnly(True)
        self.edit_output.setPlaceholderText("Auto: ./Processed")
        out_layout.addWidget(self.edit_output, 1)
        files_layout.addLayout(out_layout)

        left_layout.addWidget(files_group)

        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)

        self.btn_preview = QPushButton("Preview First File")
        self.btn_preview.setProperty("class", "info")
        self.btn_preview.clicked.connect(self.on_preview)
        actions_layout.addWidget(self.btn_preview)

        self.btn_start = QPushButton("Start Batch Process")
        self.btn_start.setProperty("class", "success")
        self.btn_start.clicked.connect(self.on_start_batch)
        actions_layout.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setProperty("class", "danger")
        self.btn_cancel.clicked.connect(self.on_cancel)
        self.btn_cancel.setEnabled(False)
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
        btn_clear_log = QPushButton("Clear Log")
        btn_clear_log.clicked.connect(self.log_text.clear)
        btn_export_log = QPushButton("Export Log")
        btn_export_log.clicked.connect(self.on_export_log)
        log_btns.addWidget(btn_clear_log)
        log_btns.addWidget(btn_export_log)
        log_btns.addStretch()
        log_layout.addLayout(log_btns)

        right_layout.addWidget(log_group)

        # Add to main
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)

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
            "Polyorder": int(self.edit_poly.text()),
            "DenoiseMethod": self.combo_denoise.currentText(),
            "BinWidth": float(self.edit_binw.text()),
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
        self.edit_poly.setText(str(cfg.get("Polyorder", 7)))
        self.combo_denoise.setCurrentText(cfg.get("DenoiseMethod", "Savitzky-Golay"))
        self.edit_binw.setText(str(cfg.get("BinWidth", 3.5)))
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
        """Load WL correction and calibration files into cache."""
        if not self.wlcorr_file or not self.wvn_file:
            return False

        try:
            wl_corr_df = rdata.read_txt_file(self.wlcorr_file, delimiter=',', header=None)
            if wl_corr_df is None:
                raise ValueError("WL correction read failed")
            if hasattr(wl_corr_df, "to_numpy"):
                self.cached_wl_corr = wl_corr_df.to_numpy().astype(np.float64).ravel()
            else:
                self.cached_wl_corr = np.asarray(wl_corr_df, dtype=np.float64).ravel()

            self.cached_wvn = rdata.getwvnfrompath(self.wvn_file).astype(np.float64).ravel()
            return True

        except Exception as e:
            self._log(f"Failed to load support files: {e}", "error")
            return False

    # Slots
    def on_load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Config", "", "JSON Files (*.json)")
        if path:
            self.config = load_config_file(path)
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
        if not self.data_files:
            QMessageBox.warning(self, "Error", "No data files selected")
            return
        if not self.wlcorr_file or not self.wvn_file:
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

            if arr.ndim == 2:
                raw_spec = arr.ravel() if arr.shape[1] == 1 else arr.mean(axis=1)
            else:
                raw_spec = arr.ravel()

            new_wvn, processed_spec = p_mean_process(raw_spec, self.cached_wl_corr, self.cached_wvn, cfg)

            self.preview_canvas.plot_preview(
                self.cached_wvn, raw_spec,
                new_wvn, processed_spec,
                os.path.basename(path)
            )
            self._log(f"Preview generated for: {os.path.basename(path)}", "success")

        except Exception as e:
            self._log(f"Preview failed: {e}", "error")
            QMessageBox.warning(self, "Error", f"Preview failed: {e}")

    def on_start_batch(self):
        """Start batch processing."""
        if not self.data_files:
            QMessageBox.warning(self, "Error", "No data files selected")
            return
        if not self.wlcorr_file or not self.wvn_file:
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
        os.makedirs(output_folder, exist_ok=True)

        # Disable controls
        self.btn_start.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(self.data_files))

        self._log(f"Starting batch processing: {len(self.data_files)} files", "info")

        # Start worker
        self.worker = BatchWorker(
            self.data_files, self.cached_wl_corr, self.cached_wvn,
            cfg, output_folder
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
