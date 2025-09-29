#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch P_Mean UI (All-in-One, parameterized)

- Editable parameters in UI (Start/Stop, Polyorder, DenoiseMethod, BinWidth, SGorder/SGframe, MAWindow, MedianKernel)
- Load/Save config JSON (p_mean_config.json by default)
- Batch process: multiple raw spectra + single WL correction + single wavenumber calibration (wvn .mat)
- Writes operations summary (including parameter snapshot) into output filename

Requirements:
    PyQt5, numpy
    Your project's utils.io.{wdata,rdata} and utils.SpectralPreprocess modules
"""

import sys
import os
import json
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QFileDialog, QMessageBox, QHBoxLayout, QListWidget, QLineEdit, QComboBox, QGroupBox, QFormLayout
)

# ---- Your project deps (kept as-is) ----
from utils.io import wdata, rdata
from utils.SpectralPreprocess import (
    Binning, Denoise, Truncate, CosmicRayRemoval,
    SpectralResponseCorrection, subtractBaseline,
    FluorescenceBackgroundSubtraction
)

# ----------------- Config helpers -----------------
def default_config() -> dict:
    """Return default config (backward-compatible)."""
    return {
        "Start": 900,
        "Stop": 1700,
        "Polyorder": 7,
        "DenoiseMethod": "Savitzky-Golay",  # ["Savitzky-Golay","Moving Average","Median Filter","None"]
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
            # merge with defaults for backward compatibility
            for k, v in default_config().items():
                cfg[k] = on_disk.get(k, v)
        except Exception as e:
            print(f"[WARN] Failed to load config: {e}")
    return cfg


def save_config_file(config: dict, config_file: str):
    """Save config JSON to file."""
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise RuntimeError(f"Failed to save config to {config_file}: {e}")


# ----------------- Processing kernel -----------------
def p_mean_process(data: np.ndarray, wl_corr: np.ndarray, wvn: np.ndarray, config: dict):
    """P-Mean pipeline using config parameters (pure functions).

    Args:
        data: 1D spectrum
        wl_corr: white-light correction array (compatible with data length or broadcastable)
        wvn: 1D wavenumber array
        config: parameters dict

    Returns:
        new_wvn: 1D wavenumber after binning
        finalSpect: processed spectrum
    """
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

    # 4) Denoise (method-specific parameters)
    method = str(config.get("DenoiseMethod", "Savitzky-Golay"))
    if method == "Savitzky-Golay":
        SGorder = int(config.get("SGorder", 2))
        SGframe = int(config.get("SGframe", 7))
        processed_spect = Denoise(binned_spect, SGorder=SGorder, SGframe=SGframe)
    elif method == "Moving Average":
        MAWindow = int(config.get("MAWindow", 5))
        MAWindow = max(1, MAWindow)
        kernel = np.ones(MAWindow, dtype=np.float64) / MAWindow
        processed_spect = np.convolve(binned_spect, kernel, mode='same')
    elif method == "Median Filter":
        from scipy.signal import medfilt
        MedianKernel = int(config.get("MedianKernel", 5))
        if MedianKernel % 2 == 0:
            MedianKernel += 1  # kernel size must be odd
        processed_spect = medfilt(binned_spect, kernel_size=MedianKernel)
    else:
        processed_spect = binned_spect

    # 5) Fluorescence background subtraction
    polyorder = int(config.get("Polyorder", 7))
    _, finalSpect = FluorescenceBackgroundSubtraction(processed_spect, polyorder)

    return new_wvn, finalSpect


# ----------------- Main UI -----------------
class BatchPMeanUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Batch P_Mean Processing")
        self.setGeometry(150, 150, 840, 560)

        # Files state
        self.data_files = []      # multiple raw spectra
        self.wlcorr_file = None   # single file
        self.wvn_file = None      # single file
        self.output_root = None

        # Config state
        self.config_path = "p_mean_config.json"
        self.config = load_config_file(self.config_path)

        self._build_ui()

    # -------- UI build --------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        # Left: parameter editor
        params_box = QGroupBox("Parameters")
        params_form = QFormLayout(params_box)

        self.edit_start = QLineEdit(str(self.config["Start"]))
        self.edit_stop = QLineEdit(str(self.config["Stop"]))
        self.edit_poly = QLineEdit(str(self.config["Polyorder"]))
        self.edit_binw = QLineEdit(str(self.config["BinWidth"]))

        self.combo_denoise = QComboBox()
        self.combo_denoise.addItems(["Savitzky-Golay", "Moving Average", "Median Filter", "None"])
        self.combo_denoise.setCurrentText(self.config.get("DenoiseMethod", "Savitzky-Golay"))
        self.combo_denoise.currentIndexChanged.connect(self._update_denoise_param_visibility)

        self.edit_sgorder = QLineEdit(str(self.config["SGorder"]))
        self.edit_sgframe = QLineEdit(str(self.config["SGframe"]))
        self.edit_mawin = QLineEdit(str(self.config["MAWindow"]))
        self.edit_medk = QLineEdit(str(self.config["MedianKernel"]))

        params_form.addRow(QLabel("Start (cm⁻¹):"), self.edit_start)
        params_form.addRow(QLabel("Stop (cm⁻¹):"), self.edit_stop)
        params_form.addRow(QLabel("Polyorder:"), self.edit_poly)
        params_form.addRow(QLabel("Denoise Method:"), self.combo_denoise)
        params_form.addRow(QLabel("BinWidth:"), self.edit_binw)
        params_form.addRow(QLabel("SG order:"), self.edit_sgorder)
        params_form.addRow(QLabel("SG frame:"), self.edit_sgframe)
        params_form.addRow(QLabel("MA Window:"), self.edit_mawin)
        params_form.addRow(QLabel("Median Kernel:"), self.edit_medk)

        # Config buttons
        cfg_btns = QHBoxLayout()
        self.btn_load_cfg = QPushButton("Load Config")
        self.btn_save_cfg = QPushButton("Save Config")
        self.btn_load_cfg.clicked.connect(self.on_load_config)
        self.btn_save_cfg.clicked.connect(self.on_save_config)
        cfg_btns.addWidget(self.btn_load_cfg)
        cfg_btns.addWidget(self.btn_save_cfg)
        params_form.addRow(cfg_btns)

        # Right: I/O panel
        right_box = QGroupBox("Batch IO")
        right = QVBoxLayout(right_box)

        # Data files
        btn_select_data = QPushButton("Select Data Files (Raw Spectrum)")
        btn_select_data.clicked.connect(self.on_select_data)
        right.addWidget(btn_select_data)

        self.list_data = QListWidget()
        right.addWidget(self.list_data)

        # WL Correction
        btn_select_wlcorr = QPushButton("Select WL Correction File")
        btn_select_wlcorr.clicked.connect(self.on_select_wlcorr)
        self.label_wlcorr = QLabel("No WL Correction file selected")
        right.addWidget(btn_select_wlcorr)
        right.addWidget(self.label_wlcorr)

        # Wavenumber calibration (wvn)
        btn_select_wvn = QPushButton("Select Calibration File (wvn .mat)")
        btn_select_wvn.clicked.connect(self.on_select_wvn)
        self.label_wvn = QLabel("No Calibration file selected")
        right.addWidget(btn_select_wvn)
        right.addWidget(self.label_wvn)

        # Output folder
        out_row = QHBoxLayout()
        self.btn_select_output = QPushButton("Select Output Folder")
        self.btn_select_output.clicked.connect(self.on_select_output_folder)
        self.lineedit_output = QLineEdit()
        self.lineedit_output.setReadOnly(True)
        out_row.addWidget(self.btn_select_output)
        out_row.addWidget(self.lineedit_output)
        right.addLayout(out_row)

        # Start
        btn_start = QPushButton("Start Batch Process")
        btn_start.clicked.connect(self.on_start_batch)
        right.addWidget(btn_start)

        # Status
        self.label_info = QLabel("Config loaded from: " + os.path.abspath(self.config_path))
        self.label_status = QLabel("Status: Waiting")
        right.addWidget(self.label_info)
        right.addWidget(self.label_status)

        # Layout mount
        root.addWidget(params_box, 0)
        root.addWidget(right_box, 1)

        # Initial visibility for denoise controls
        self._update_denoise_param_visibility()

    # -------- UI helpers --------
    def _gather_config_from_ui(self) -> dict:
        """Read config from widgets with validation."""
        try:
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
        except Exception as e:
            raise ValueError(f"Parameter parse error: {e}")

        if cfg["Stop"] <= cfg["Start"]:
            raise ValueError("Stop must be greater than Start.")
        if cfg["DenoiseMethod"] == "Savitzky-Golay" and (cfg["SGframe"] < 3 or cfg["SGframe"] % 2 == 0):
            raise ValueError("SGframe must be an odd integer >= 3.")
        if cfg["DenoiseMethod"] == "Median Filter" and cfg["MedianKernel"] < 1:
            raise ValueError("MedianKernel must be >=1 (odd is recommended).")
        if cfg["DenoiseMethod"] == "Moving Average" and cfg["MAWindow"] < 1:
            raise ValueError("MAWindow must be >=1.")
        if cfg["BinWidth"] <= 0:
            raise ValueError("BinWidth must be > 0.")
        return cfg

    def _apply_config_to_ui(self, cfg: dict):
        """Write config values into widgets."""
        self.edit_start.setText(str(cfg.get("Start", 900)))
        self.edit_stop.setText(str(cfg.get("Stop", 1700)))
        self.edit_poly.setText(str(cfg.get("Polyorder", 7)))
        self.combo_denoise.setCurrentText(cfg.get("DenoiseMethod", "Savitzky-Golay"))
        self.edit_binw.setText(str(cfg.get("BinWidth", 3.5)))
        self.edit_sgorder.setText(str(cfg.get("SGorder", 2)))
        self.edit_sgframe.setText(str(cfg.get("SGframe", 7)))
        self.edit_mawin.setText(str(cfg.get("MAWindow", 5)))
        self.edit_medk.setText(str(cfg.get("MedianKernel", 5)))
        self._update_denoise_param_visibility()

    def _update_denoise_param_visibility(self):
        """Show/hide method-specific params."""
        method = self.combo_denoise.currentText()
        is_sg = (method == "Savitzky-Golay")
        is_ma = (method == "Moving Average")
        is_md = (method == "Median Filter")

        self.edit_sgorder.setVisible(is_sg)
        self.edit_sgframe.setVisible(is_sg)
        # Find their labels from form layout and toggle too
        self._toggle_form_row_label(self.edit_sgorder, is_sg)
        self._toggle_form_row_label(self.edit_sgframe, is_sg)

        self.edit_mawin.setVisible(is_ma)
        self._toggle_form_row_label(self.edit_mawin, is_ma)

        self.edit_medk.setVisible(is_md)
        self._toggle_form_row_label(self.edit_medk, is_md)

    def _toggle_form_row_label(self, editor: QLineEdit, visible: bool):
        """Find the label widget paired with editor in parent FormLayout and toggle its visibility."""
        form = editor.parentWidget().layout() if editor.parentWidget() else None
        if not isinstance(form, QFormLayout):
            # It might be indirect; traverse a bit
            parent = editor.parentWidget()
            while parent and not isinstance(parent.layout(), QFormLayout):
                parent = parent.parentWidget()
            form = parent.layout() if parent else None
        if isinstance(form, QFormLayout):
            # search for the editor widget in rows
            for i in range(form.rowCount()):
                itemW = form.itemAt(i, QFormLayout.FieldRole)
                if itemW and itemW.widget() is editor:
                    itemL = form.itemAt(i, QFormLayout.LabelRole)
                    if itemL and itemL.widget():
                        itemL.widget().setVisible(visible)
                    break

    # -------- Slots --------
    def on_load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Config File", "",
                                              "JSON Files (*.json);;All Files (*)")
        if not path:
            return
        self.config_path = path
        self.config = load_config_file(path)
        self._apply_config_to_ui(self.config)
        self.label_info.setText("Config loaded from: " + os.path.abspath(path))

    def on_save_config(self):
        """Save current UI params to JSON."""
        try:
            cfg = self._gather_config_from_ui()
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save Config As", self.config_path,
                                              "JSON Files (*.json);;All Files (*)")
        if not path:
            return
        try:
            save_config_file(cfg, path)
            self.config_path = path
            self.config = cfg
            self.label_info.setText("Config saved to: " + os.path.abspath(path))
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def on_select_data(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Data Files", "",
                                                "Text Files (*.txt *.csv);;All Files (*)")
        if files:
            self.data_files = files
            self.list_data.clear()
            for f in files:
                self.list_data.addItem(f)

    def on_select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_root = folder
            self.lineedit_output.setText(folder)

    def on_select_wlcorr(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select WL Correction File", "",
                                              "Text/CSV Files (*.txt *.csv);;All Files (*)")
        if file:
            self.wlcorr_file = file
            self.label_wlcorr.setText(f"WL Correction: {file}")

    def on_select_wvn(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Calibration File (wvn)", "",
                                              "MAT Files (*.mat);;All Files (*)")
        if file:
            self.wvn_file = file
            self.label_wvn.setText(f"Calibration (wvn): {file}")

    def on_start_batch(self):
        # Validate inputs
        if len(self.data_files) == 0:
            QMessageBox.warning(self, "Error", "Please select at least one Data file.")
            return
        if not self.wlcorr_file:
            QMessageBox.warning(self, "Error", "Please select a WL Correction file.")
            return
        if not self.wvn_file:
            QMessageBox.warning(self, "Error", "Please select a Calibration file (wvn .mat).")
            return
        try:
            cfg = self._gather_config_from_ui()
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        # Output directory
        base_dir = os.path.normpath(os.path.dirname(self.data_files[0]))
        if self.output_root is None or self.output_root == "":
            output_folder = os.path.abspath(os.path.join(base_dir, "Processed"))
        else:
            output_folder = os.path.abspath(self.output_root)
        os.makedirs(output_folder, exist_ok=True)

        # Load WL correction
        try:
            wl_corr_df = rdata.read_txt_file(self.wlcorr_file, delimiter=',', header=None)
            if wl_corr_df is None:
                raise RuntimeError("WL correction file read returned None.")
            if hasattr(wl_corr_df, "to_numpy"):
                wl_corr = wl_corr_df.to_numpy().astype(np.float64).ravel()
            else:
                wl_corr = np.asarray(wl_corr_df, dtype=np.float64).ravel()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error reading WL Correction file: {e}")
            return

        # Load wavenumber (wvn) once
        try:
            wvn = rdata.getwvnfrompath(self.wvn_file).astype(np.float64).ravel()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error reading Calibration file: {e}")
            return

        # Build ops summary (short, filename-friendly)
        ops_kv = [
            f"Start{cfg['Start']}",
            f"Stop{cfg['Stop']}",
            f"P{cfg['Polyorder']}",
            f"DN{cfg['DenoiseMethod'].replace(' ', '')}",
            f"BW{cfg['BinWidth']}",
        ]
        if cfg["DenoiseMethod"] == "Savitzky-Golay":
            ops_kv += [f"SGO{cfg['SGorder']}", f"SGF{cfg['SGframe']}"]
        elif cfg["DenoiseMethod"] == "Moving Average":
            ops_kv += [f"MAW{cfg['MAWindow']}"]
        elif cfg["DenoiseMethod"] == "Median Filter":
            ops_kv += [f"MDK{cfg['MedianKernel']}"]
        ops_summary = "BatchPMean_" + "_".join(ops_kv)

        # Process each data file
        processed_files = []
        fail_count = 0
        self.label_status.setText("Status: Running ...")
        QApplication.processEvents()

        for path in self.data_files:
            try:
                data_df = rdata.load_spectrum_data(path)
                # robust to DataFrame / ndarray
                if hasattr(data_df, "to_numpy"):
                    arr = data_df.to_numpy()
                else:
                    arr = np.asarray(data_df)
                arr = np.asarray(arr, dtype=np.float64)

                # Collapse to 1D if needed (take mean across columns)
                if arr.ndim == 2:
                    if arr.shape[1] == 1:
                        raw_spec = arr.ravel()
                    else:
                        raw_spec = arr.mean(axis=1)
                else:
                    raw_spec = arr.ravel()

                # Process
                new_wvn, processed_spec = p_mean_process(raw_spec, wl_corr, wvn, cfg)
                output_data = np.column_stack((new_wvn, processed_spec))

                # Prefix only base name
                prefix = os.path.basename(path)
                out_path = wdata.save_data(
                    output_data, prefix=prefix, operations=ops_summary,
                    base_dir=output_folder, file_ext="txt",
                    header="Wavenumber,SpectralIntensity"
                )
                processed_files.append(out_path)
                print(f"[OK] {path} -> {out_path}")
            except Exception as e:
                fail_count += 1
                print(f"[ERR] {path}: {e}")

        self.label_status.setText("Status: Done")
        msg = f"Batch processing complete.\nSuccess: {len(processed_files)}"
        if fail_count:
            msg += f"\nFailed: {fail_count} (see console)"
        if processed_files:
            msg += "\n\nProcessed files:\n" + "\n".join(processed_files[:20])
            if len(processed_files) > 20:
                msg += f"\n... and {len(processed_files)-20} more"
        QMessageBox.information(self, "Batch Process", msg)


# ----------------- Entrypoint -----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = BatchPMeanUI()
    win.show()
    sys.exit(app.exec_())
