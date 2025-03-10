import fnmatch
import json
import sys
import os
from datetime import datetime

from utils.io import rdata, wdata
import numpy as np
import pandas as pd  # Ensure pandas is imported
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
                             QLineEdit, QVBoxLayout, QFileDialog, QMessageBox,
                             QHBoxLayout, QComboBox, QListWidget)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.SpectralPreprocess import (Binning, Denoise, Truncate, CosmicRayRemoval,
                                      SpectralResponseCorrection, subtractBaseline,
                                      FluorescenceBackgroundSubtraction)
from scipy.signal import medfilt


# --- Additional denoising functions ---
def moving_average(data, window=5):
    # Convolve with a uniform window
    return np.convolve(data, np.ones(window)/window, mode='same')


def median_filter(data, kernel_size=5):
    return medfilt(data, kernel_size=kernel_size)


class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)  # Save Figure object as self.fig
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.plotted_lines = []

    def plot(self, data):
        self.axes.clear()
        # If data is a tuple (x, y) then plot x-y curve; otherwise, plot y only.
        if isinstance(data, tuple) and len(data) == 2:
            x, y = data
            self.axes.plot(x, y)
        else:
            self.axes.plot(data)
        self.axes.set_title('Data Plots')
        self.draw()

    def draw_lines(self, positions, colors):
        # Clear existing lines
        for line in self.plotted_lines:
            line.remove()
        self.plotted_lines.clear()
        # Draw new lines and store their references
        for pos, color in zip(positions, colors):
            line = self.axes.axhline(y=pos, color=color, linewidth=1)
            self.plotted_lines.append(line)
        self.draw()


class P_Mean_Process_UI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spectrum Data Process")
        self.setGeometry(100, 100, 900, 600)

        # Initial simulated data: wavenumber and spectrum
        self.wvnFull = np.linspace(400, 900, 500)
        self.rawSpect = np.sin(self.wvnFull / 100) + np.random.normal(0, 0.1, self.wvnFull.shape)
        self.current_spect = self.rawSpect.copy()
        self.current_wvn = self.wvnFull.copy()

        # Dummy WL Correction array (shape=(500,1))
        self.wlCorr = np.ones((500, 1)) * 1.2

        # Record operations (for file naming)
        self.operations = []

        # History: store processing states as dictionaries (with snapshot of operations)
        self.history = []

        # Standard processing steps in fixed order
        self.processing_steps = [
            "SubtractBaseline",
            "SpectralResponseCorrection",
            "CosmicRayRemoval",
            "Truncate",
            "Binning",
            "Denoise",
            "FluorescenceBackgroundSubtraction"
        ]
        self.current_step_index = 0

        self.initUI()
        self.add_history("Initial")

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # PlotCanvas instance
        self.canvas = PlotCanvas(self, width=7, height=5, dpi=100)
        layout.addWidget(self.canvas)
        self.update_plot()

        # Parameter input area (Start, Stop, Polyorder)
        param_layout = QHBoxLayout()
        self.label_start = QLabel("Start:")
        param_layout.addWidget(self.label_start)
        self.edit_start = QLineEdit("900")
        param_layout.addWidget(self.edit_start)
        self.label_stop = QLabel("Stop:")
        param_layout.addWidget(self.label_stop)
        self.edit_stop = QLineEdit("1700")
        param_layout.addWidget(self.edit_stop)
        self.label_polyorder = QLabel("Polyorder:")
        param_layout.addWidget(self.label_polyorder)
        self.edit_polyorder = QLineEdit("7")
        param_layout.addWidget(self.edit_polyorder)
        layout.addLayout(param_layout)

        # Denoise method selection (for Denoise step)
        denoise_layout = QHBoxLayout()
        self.label_denoise = QLabel("Denoise Method:")
        denoise_layout.addWidget(self.label_denoise)
        self.combo_denoise = QComboBox()
        self.combo_denoise.addItems(["Savitzky-Golay", "Moving Average", "Median Filter"])
        denoise_layout.addWidget(self.combo_denoise)
        layout.addLayout(denoise_layout)

        # Label to show current saved file name
        self.label_saved_file = QLabel("Current File Saved: None")
        layout.addWidget(self.label_saved_file)

        # Label to show next step
        self.label_next_step = QLabel("Next Step: " + self.processing_steps[self.current_step_index])
        layout.addWidget(self.label_next_step)

        # History list for process visualization
        history_layout = QVBoxLayout()
        history_label = QLabel("Processing History:")
        history_layout.addWidget(history_label)
        self.history_list = QListWidget()
        history_layout.addWidget(self.history_list)
        layout.addLayout(history_layout)

        # Navigation buttons (Previous, Next, Save, Load)
        nav_layout = QHBoxLayout()
        btn_previous = QPushButton("Previous")
        btn_previous.clicked.connect(self.on_previous_step)
        nav_layout.addWidget(btn_previous)
        btn_next = QPushButton("Next")
        btn_next.clicked.connect(self.on_next_step)
        nav_layout.addWidget(btn_next)
        btn_save_fig = QPushButton("Save Figure")
        btn_save_fig.clicked.connect(self.on_save_figure)
        nav_layout.addWidget(btn_save_fig)
        btn_save_data = QPushButton("Save Data")
        btn_save_data.clicked.connect(self.on_save_data)
        nav_layout.addWidget(btn_save_data)
        btn_load_rdata = QPushButton("Load Data Files")
        btn_load_rdata.clicked.connect(self.on_load_rdata_files)
        nav_layout.addWidget(btn_load_rdata)
        layout.addLayout(nav_layout)

    def update_plot(self):
        if self.current_wvn is not None and len(self.current_wvn) == len(self.current_spect):
            self.canvas.plot((self.current_wvn, self.current_spect))
        else:
            self.canvas.plot(self.current_spect)

    def add_history(self, op_name):
        state = {
            "op": op_name,
            "wvn": np.copy(self.current_wvn),
            "spect": np.copy(self.current_spect),
            "ops": self.operations.copy(),  # Save a snapshot of operations
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        self.history.append(state)
        self.history_list.addItem(f"{op_name} ({state['timestamp']})")
        if self.current_step_index < len(self.processing_steps):
            self.label_next_step.setText("Next Step: " + self.processing_steps[self.current_step_index])
        else:
            self.label_next_step.setText("Processing Complete")

    def on_previous_step(self):
        # Go back one step if available and remove the corresponding history entry.
        if len(self.history) < 3:
            QMessageBox.warning(self, "Error", "No previous state available.")
            return
        # Remove the last state from history and remove its entry from the list.
        self.history.pop()
        self.history_list.takeItem(self.history_list.count() - 1)
        last_state = self.history[-1]
        self.current_wvn = np.copy(last_state["wvn"])
        self.current_spect = np.copy(last_state["spect"])
        self.operations = last_state["ops"].copy()
        if self.current_step_index > 0:
            self.current_step_index -= 1
        self.update_plot()
        self.label_next_step.setText("Next Step: " + self.processing_steps[self.current_step_index])

    def on_next_step(self):
        if self.current_step_index >= len(self.processing_steps):
            QMessageBox.information(self, "Info", "Processing complete.")
            return
        step = self.processing_steps[self.current_step_index]
        # Apply the processing step according to the standardized order.
        if step == "SubtractBaseline":
            self.current_spect = subtractBaseline(self.current_spect)
            self.operations.append("SubtractBaseline")
        elif step == "SpectralResponseCorrection":
            self.current_spect = SpectralResponseCorrection(self.wlCorr, self.current_spect)
            self.operations.append("SpectralResponseCorrection")
        elif step == "CosmicRayRemoval":
            self.current_spect = CosmicRayRemoval(self.current_spect)
            self.operations.append("CosmicRayRemoval")
        elif step == "Truncate":
            try:
                start = float(self.edit_start.text())
                stop = float(self.edit_stop.text())
            except ValueError:
                QMessageBox.warning(self, "Error", "Start and Stop must be numbers!")
                return
            self.current_wvn, self.current_spect = Truncate(start, stop, self.wvnFull, self.current_spect)
            self.operations.append(f"Truncate({start}-{stop})")
        elif step == "Binning":
            if self.current_wvn.size == 0:
                QMessageBox.warning(self, "Warning", "Current data is empty!")
                return
            start = self.current_wvn[0]
            stop = self.current_wvn[-1]
            binned_spect, new_wvn = Binning(start, stop, self.current_wvn, self.current_spect, binwidth=3.5)
            self.current_spect = binned_spect
            self.current_wvn = new_wvn
            self.operations.append("Binning")
        elif step == "Denoise":
            method = self.combo_denoise.currentText()
            if method == "Savitzky-Golay":
                self.current_spect = Denoise(self.current_spect, SGorder=2, SGframe=7)
            elif method == "Moving Average":
                self.current_spect = moving_average(self.current_spect, window=5)
            elif method == "Median Filter":
                self.current_spect = median_filter(self.current_spect, kernel_size=5)
            self.operations.append(f"Denoise({method})")
        elif step == "FluorescenceBackgroundSubtraction":
            try:
                polyorder = int(self.edit_polyorder.text())
            except ValueError:
                QMessageBox.warning(self, "Error", "Polyorder must be an integer!")
                return
            base, finalSpect = FluorescenceBackgroundSubtraction(self.current_spect, polyorder)
            self.current_spect = finalSpect
            self.operations.append(f"FluorescenceBackgroundSubtraction(polyorder={polyorder})")
        else:
            QMessageBox.warning(self, "Error", "Unknown processing step.")
            return

        self.add_history(step)
        self.current_step_index += 1
        if self.current_step_index < len(self.processing_steps):
            self.label_next_step.setText("Next Step: " + self.processing_steps[self.current_step_index])
        else:
            self.label_next_step.setText("Processing Complete")
        self.update_plot()

    def on_save_figure(self):
        try:
            filepath = wdata.save_figure(self.canvas.fig, self.operations, base_dir=".", file_ext="png")
            self.label_saved_file.setText("Saved Figure: " + filepath)
            QMessageBox.information(self, "Saved", f"Figure saved to {filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save figure: {e}")

    def on_save_data(self):
        if self.current_wvn is None or self.current_spect is None:
            QMessageBox.warning(self, "Error", "Empty data, cannot save!")
            return
        try:
            wvn_filepath = wdata.save_data(self.current_wvn.reshape(-1, 1), self.operations,
                                           base_dir=".", file_ext="csv", header="Wavelength")
            spect_filepath = wdata.save_data(self.current_spect.reshape(-1, 1), self.operations,
                                             base_dir=".", file_ext="csv", header="SpectralIntensity")
            QMessageBox.information(self, "Saved",
                                    f"Data saved to:\n{wvn_filepath}\n{spect_filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save data: {e}")

    def on_load_rdata_files(self):
        data_file, _ = QFileDialog.getOpenFileName(self, "Select Lipid FP Data", "",
                                                   "Text Files (*.txt);;All Files (*)")
        if not data_file:
            return
        wlcorr_file, _ = QFileDialog.getOpenFileName(self, "Select WL Correction Data", "",
                                                     "Text Files (*.txt);;All Files (*)")
        if not wlcorr_file:
            return
        wvn_file, _ = QFileDialog.getOpenFileName(self, "Select Calibration File", "",
                                                  "MAT Files (*.mat);;All Files (*)")
        if not wvn_file:
            return

        try:
            data_df = rdata.read_txt_file(data_file, delimiter=',', header=None)
            if data_df is None:
                QMessageBox.warning(self, "Error", "Can't read data file")
                return
            if data_df.shape[1] < 2:
                QMessageBox.warning(self, "Error", "Data file format error, must have at least 2 columns.")
                return
            self.current_spect = data_df.iloc[:, 1:].mean(axis=1).to_numpy().astype(np.float64)

            wl_corr = rdata.read_txt_file(wlcorr_file)
            if wl_corr is None:
                QMessageBox.warning(self, "Error", "Can't read WL Correction file")
                return
            self.wlCorr = wl_corr.to_numpy().astype(np.float64)

            self.wvnFull = rdata.getwvnfrompath(wvn_file).flatten().astype(np.float64)
            self.current_wvn = self.wvnFull.copy()

            self.operations.append("LoadData")
            self.update_plot()
            QMessageBox.information(self, "Loaded", "rData files loaded successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to read rData files: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = P_Mean_Process_UI()
    window.show()
    sys.exit(app.exec_())
