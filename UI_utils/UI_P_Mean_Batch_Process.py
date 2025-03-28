import sys
import os
import json
from datetime import datetime

import numpy as np
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QFileDialog, QMessageBox, QHBoxLayout, QListWidget)
from utils.io import wdata, rdata
from utils.SpectralPreprocess import (Binning, Denoise, Truncate, CosmicRayRemoval,
                                      SpectralResponseCorrection, subtractBaseline,
                                      FluorescenceBackgroundSubtraction)


# Function to load configuration from p_mean_config.json
def load_config(config_file="p_mean_config.json"):
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config
        except Exception as e:
            print("Failed to load config:", e)
            return {}
    else:
        print("Config file not found.")
        return {}


# Dummy P_Mean processing function using configuration parameters.
def p_mean_process(data, wl_corr, wvn, config):
    # Apply a chain of processing steps using the config parameters.
    spect = subtractBaseline(data)
    spect = SpectralResponseCorrection(wl_corr, spect)
    spect = CosmicRayRemoval(spect)
    start = config.get("Start", 900)
    stop = config.get("Stop", 1700)
    wvn_trunc, spect_trunc = Truncate(start, stop, wvn, spect)
    binned_spect, new_wvn = Binning(wvn_trunc[0], wvn_trunc[-1], wvn_trunc, spect_trunc, binwidth=3.5)
    denoise_method = config.get("DenoiseMethod", "Savitzky-Golay")
    if denoise_method == "Savitzky-Golay":
        processed_spect = Denoise(binned_spect, SGorder=2, SGframe=7)
    elif denoise_method == "Moving Average":
        processed_spect = np.convolve(binned_spect, np.ones(5) / 5, mode='same')
    elif denoise_method == "Median Filter":
        from scipy.signal import medfilt
        processed_spect = medfilt(binned_spect, kernel_size=5)
    else:
        processed_spect = binned_spect
    polyorder = config.get("Polyorder", 7)
    base, finalSpect = FluorescenceBackgroundSubtraction(processed_spect, polyorder)
    return new_wvn, finalSpect


class BatchPMeanUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Batch P_Mean Processing")
        self.setGeometry(150, 150, 600, 500)

        self.config = load_config()
        # Data files: multi-select allowed.
        self.data_files = []
        # WL Correction and wvn: single file selections.
        self.wlcorr_file = None
        self.wvn_file = None

        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.label_info = QLabel("Batch P_Mean Processing using configuration:")
        layout.addWidget(self.label_info)

        btn_load_config = QPushButton("Load Config")
        btn_load_config.clicked.connect(self.on_load_config)
        layout.addWidget(btn_load_config)

        # Data file selection (multi-select)
        btn_select_data = QPushButton("Select Data Files (Raw Spectrum)")
        btn_select_data.clicked.connect(self.on_select_data)
        layout.addWidget(btn_select_data)
        self.list_data = QListWidget()
        layout.addWidget(self.list_data)

        # WL Correction file selection (single file)
        btn_select_wlcorr = QPushButton("Select WL Correction File")
        btn_select_wlcorr.clicked.connect(self.on_select_wlcorr)
        layout.addWidget(btn_select_wlcorr)
        self.label_wlcorr = QLabel("No WL Correction file selected")
        layout.addWidget(self.label_wlcorr)

        # Calibration (wvn) file selection (single file)
        btn_select_wvn = QPushButton("Select Calibration File (wvn)")
        btn_select_wvn.clicked.connect(self.on_select_wvn)
        layout.addWidget(btn_select_wvn)
        self.label_wvn = QLabel("No Calibration file selected")
        layout.addWidget(self.label_wvn)

        btn_start = QPushButton("Start Batch Process")
        btn_start.clicked.connect(self.on_start_batch)
        layout.addWidget(btn_start)

        self.label_status = QLabel("Status: Waiting")
        layout.addWidget(self.label_status)

    def on_load_config(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Choose Config File", "",
                                                   "JSON Files (*.json);;All Files (*)", options=options)
        self.config = load_config(file_name)
        self.label_info.setText("Config loaded:\n" + json.dumps(self.config, indent=2))

    def on_select_data(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Data Files", "", "Text Files (*.txt);;All Files (*)")
        if files:
            self.data_files = files
            self.list_data.clear()
            for f in files:
                self.list_data.addItem(f)

    def on_select_wlcorr(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select WL Correction File", "",
                                              "Text Files (*.txt *.csv);;All Files (*)")
        if file:
            self.wlcorr_file = file
            self.label_wlcorr.setText(f"WL Correction: {file}")

    def on_select_wvn(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Calibration File", "", "MAT Files (*.mat);;All Files (*)")
        if file:
            self.wvn_file = file
            self.label_wvn.setText(f"Calibration (wvn): {file}")

    def on_start_batch(self):
        if len(self.data_files) == 0:
            QMessageBox.warning(self, "Error", "Please select at least one Data file.")
            return
        if not self.wlcorr_file:
            QMessageBox.warning(self, "Error", "Please select a WL Correction file.")
            return
        if not self.wvn_file:
            QMessageBox.warning(self, "Error", "Please select a Calibration file.")
            return

        # Build output folder based on directory of first data file.
        base_dir = os.path.normpath(os.path.dirname(self.data_files[0]))
        output_folder = os.path.join(base_dir, "Processed")
        output_folder = os.path.abspath(output_folder)
        os.makedirs(output_folder, exist_ok=True)
        processed_files = []

        # Load the single WL Correction and wvn files once.
        try:
            wl_corr_df = rdata.read_txt_file(self.wlcorr_file, delimiter=',', header=None)
            if wl_corr_df is None:
                raise Exception("Failed to read WL Correction file.")
            wl_corr = wl_corr_df.to_numpy().astype(np.float64)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error reading WL Correction file: {e}")
            return

        try:
            wvn = rdata.getwvnfrompath(self.wvn_file).flatten().astype(np.float64)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error reading Calibration file: {e}")
            return

        for i in range(len(self.data_files)):
            try:
                # Load raw spectrum data from each file.
                data_df = rdata.load_spectrum_data(self.data_files[i])
                raw_spec = data_df.flattern().astype(np.float64)
                # raw_spec = data_df.iloc[:, 1:].mean(axis=1).to_numpy().astype(np.float64)

                # Process using the p_mean_process function.
                new_wvn, processed_spec = p_mean_process(raw_spec, wl_corr, wvn, self.config)
                output_data = np.column_stack((new_wvn, processed_spec))
                # Use only the base filename as prefix.
                prefix = os.path.basename(self.data_files[i])
                ops_summary = "BatchPMean_" + "_".join(f"{k}{v}" for k, v in self.config.items())
                out_filepath = wdata.save_data(output_data, prefix=prefix, operations=ops_summary,
                                               base_dir=output_folder, file_ext="txt",
                                               header="Wavenumber,SpectralIntensity")
                processed_files.append(out_filepath)
                print(f"Processed {self.data_files[i]} -> {out_filepath}")
            except Exception as e:
                print(f"Error processing file {self.data_files[i]}: {e}")
        self.label_status.setText("Batch processing complete.")
        QMessageBox.information(self, "Batch Process",
                                "Batch processing complete.\nProcessed files:\n" + "\n".join(processed_files))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BatchPMeanUI()
    window.show()
    sys.exit(app.exec_())
