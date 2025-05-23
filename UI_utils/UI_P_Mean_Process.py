import json
import sys
from datetime import datetime

from utils.io import rdata, wdata
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
                             QLineEdit, QVBoxLayout, QFileDialog, QMessageBox,
                             QHBoxLayout, QComboBox, QListWidget, QDialog)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.signal import medfilt
from UI_utils.UI_Config_Manager import ConfigManager

from utils.SpectralPreprocess import (Binning, Denoise, Truncate, CosmicRayRemoval,
                                      SpectralResponseCorrection, subtractBaseline,
                                      FluorescenceBackgroundSubtraction, Normalize)

config_manager = ConfigManager()
# --- Additional denoising functions ---
def moving_average(data, window=5):
    return np.convolve(data, np.ones(window) / window, mode='same')


def median_filter(data, kernel_size=5):
    return medfilt(data, kernel_size=kernel_size)


# Configuration file name
CONFIG_FILE = "p_mean_config.json"


class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)  # Save Figure object as self.fig
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.plotted_lines = []

    def plot(self, data):
        self.axes.clear()
        if isinstance(data, tuple) and len(data) == 2:
            x, y = data
            self.axes.plot(x, y)
        else:
            self.axes.plot(data)
        self.axes.set_title('Data Plots')
        self.draw()

    def draw_lines(self, positions, colors):
        for line in self.plotted_lines:
            line.remove()
        self.plotted_lines.clear()
        for pos, color in zip(positions, colors):
            line = self.axes.axhline(y=pos, color=color, linewidth=1)
            self.plotted_lines.append(line)
        self.draw()


class P_Mean_Process_UI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_system = config_manager.params.get("System", "")
        print("Current System:", self.current_system)

        self.setWindowTitle("Spectrum Data Process")
        self.setGeometry(100, 100, 900, 600)

        # Initial simulated data
        self.wvnFull = np.zeros([100, 1])
        self.rawSpect = np.zeros(self.wvnFull.shape)
        self.current_spect = self.rawSpect.copy()
        self.current_wvn = self.wvnFull.copy()

        self.wlCorr = np.ones((500, 1)) * 1.2

        self.operations = []
        self.history = []
        self.processing_steps = [
            "Upload File",
            "SubtractBaseline",
            "SpectralResponseCorrection",
            "CosmicRayRemoval",
            "Truncate",
            "Binning",
            "Denoise",
            "Polyfit",
            "FluorescenceBackgroundSubtraction",
            "Normalization"
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

        # Denoise method selection (visible only in "Denoise" step)
        denoise_layout = QHBoxLayout()
        self.label_denoise = QLabel("Denoise Method:")
        denoise_layout.addWidget(self.label_denoise)
        self.combo_denoise = QComboBox()
        self.combo_denoise.addItems(["Savitzky-Golay", "Moving Average", "Median Filter"])
        denoise_layout.addWidget(self.combo_denoise)
        layout.addLayout(denoise_layout)
        self.label_denoise.setVisible(False)
        self.combo_denoise.setVisible(False)

        # # Comparison option: only displayed during FBS step.
        # compare_layout = QHBoxLayout()
        # self.label_compare = QLabel("Generate Comparison Plot:")
        # compare_layout.addWidget(self.label_compare)
        # self.chk_compare = QComboBox()
        # self.chk_compare.addItems(["Yes", "No"])
        # self.chk_compare.setCurrentText("Yes")
        # compare_layout.addWidget(self.chk_compare)
        # layout.addLayout(compare_layout)
        # # Initially, hide the comparison option until reaching FBS step.
        # self.label_compare.setVisible(False)
        # self.chk_compare.setVisible(False)

        # Configuration buttons (Save Config and Load Config)
        config_layout = QHBoxLayout()
        btn_save_config = QPushButton("Save Config")
        btn_save_config.clicked.connect(self.on_save_config)
        config_layout.addWidget(btn_save_config)
        btn_load_config = QPushButton("Load Config")
        btn_load_config.clicked.connect(self.on_load_config)
        config_layout.addWidget(btn_load_config)
        layout.addLayout(config_layout)

        # Saved file label
        self.label_saved_file = QLabel("Current File Saved: None")
        layout.addWidget(self.label_saved_file)

        # Current Step Label
        self.label_current_step = QLabel("Current Step: " + self.processing_steps[self.current_step_index])
        layout.addWidget(self.label_current_step)

        # Next Step label
        self.label_next_step = QLabel("Next Step: " + self.processing_steps[self.current_step_index])
        layout.addWidget(self.label_next_step)

        # History list
        history_layout = QVBoxLayout()
        history_label = QLabel("Processing History:")
        history_layout.addWidget(history_label)
        self.history_list = QListWidget()
        history_layout.addWidget(self.history_list)
        # layout.addLayout(history_layout)

        # Navigation buttons (Previous, Next, Save Figure, Save Data, Load Data Files)
        nav_layout = QHBoxLayout()
        self.btn_previous = QPushButton("Previous")
        self.btn_previous.clicked.connect(self.on_previous_step)
        self.btn_previous.setVisible(False)
        nav_layout.addWidget(self.btn_previous)


        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self.on_next_step)
        self.btn_next.setVisible(False)
        nav_layout.addWidget(self.btn_next)

        self.btn_save_fig = QPushButton("Save Figure")
        self.btn_save_fig.clicked.connect(self.on_save_figure)
        self.btn_save_fig.setVisible(False)
        nav_layout.addWidget(self.btn_save_fig)

        self.btn_save_data = QPushButton("Save Data")
        self.btn_save_data.clicked.connect(self.on_save_data)
        self.btn_save_data.setVisible(False)
        nav_layout.addWidget(self.btn_save_data)

        btn_load_rdata = QPushButton("Load Data Files")
        btn_load_rdata.clicked.connect(self.on_load_rdata_files)
        nav_layout.addWidget(btn_load_rdata)
        layout.addLayout(nav_layout)

    def update_plot(self):
        if self.current_wvn is not None and len(self.current_wvn) == len(self.current_spect):
            self.canvas.plot((self.current_wvn, self.current_spect))
        else:
            self.canvas.plot(self.current_spect)

    def update_step_ui(self):
        # Only show the denoise method selection when current step is "Denoise"
        if self.current_step_index < len(self.processing_steps) and \
           self.processing_steps[self.current_step_index] == "Denoise":
            self.label_denoise.setVisible(True)
            self.combo_denoise.setVisible(True)
        else:
            self.label_denoise.setVisible(False)
            self.combo_denoise.setVisible(False)


    def add_history(self, op_name):
        state = {
            "op": op_name,
            "wvn": np.copy(self.current_wvn),
            "spect": np.copy(self.current_spect),
            "ops": self.operations.copy(),
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        self.history.append(state)
        self.history_list.addItem(f"{op_name} ({state['timestamp']})")
        if self.current_step_index < len(self.processing_steps):
            self.label_next_step.setText("Next Step: " + self.processing_steps[self.current_step_index])
        else:
            self.label_next_step.setText("Processing Complete")
        self.update_step_ui()

    def on_save_config(self):
        # Build configuration from current UI parameters.
        config = {}
        try:
            config["Start"] = float(self.edit_start.text())
            config["Stop"] = float(self.edit_stop.text())
            config["Polyorder"] = int(self.edit_polyorder.text())
            config["DenoiseMethod"] = self.combo_denoise.currentText()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Parameter input error: {e}")
            return

        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Config File", "",
                                                  "JSON Files (*.json);;All Files (*)", options=options)
        if fileName:
            try:
                with open(fileName, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=4)
                QMessageBox.information(self, "Config Saved", f"Configuration saved successfully to:\n{fileName}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save config: {e}")

    def on_load_config(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self, "Load Config File", "",
                                                  "JSON Files (*.json);;All Files (*)", options=options)
        if fileName:
            try:
                with open(fileName, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.edit_start.setText(str(config.get("Start", 900)))
                self.edit_stop.setText(str(config.get("Stop", 1700)))
                self.edit_polyorder.setText(str(config.get("Polyorder", 7)))
                self.combo_denoise.setCurrentText(config.get("DenoiseMethod", "Savitzky-Golay"))
                QMessageBox.information(self, "Config Loaded", "Configuration loaded successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load config: {e}")
        else:
            QMessageBox.warning(self, "Error", "No configuration file selected.")

    def on_previous_step(self):
        if len(self.history) < 3:
            QMessageBox.warning(self, "Error", "No previous state available.")
            return
        self.history.pop()
        self.history_list.takeItem(self.history_list.count() - 1)
        last_state = self.history[-1]
        self.current_wvn = np.copy(last_state["wvn"])
        self.current_spect = np.copy(last_state["spect"])
        self.operations = last_state["ops"].copy()
        if self.current_step_index > 0:
            self.current_step_index -= 1

        # Update plot depending on whether the last step was 'Polyfit'
        step = self.processing_steps[self.current_step_index - 1] if self.current_step_index - 1 >= 0 else ""
        if step == "Polyfit":
            try:
                polyorder = int(self.edit_polyorder.text())
            except ValueError:
                QMessageBox.warning(self, "Error", "Polyorder must be an integer!")
                return
            base, _ = FluorescenceBackgroundSubtraction(self.current_spect, polyorder)
            x = self.current_wvn if self.current_wvn is not None and len(self.current_wvn) == len(self.current_spect) else np.arange(len(self.current_spect))
            self.canvas.axes.clear()
            self.canvas.axes.plot(x, self.current_spect, label="Spectrum", color="blue", linestyle='-')
            self.canvas.axes.plot(x, base, label="Polyfit Line", color="red", linestyle='--')
            self.canvas.axes.set_title("Polyfit Overview")
            self.canvas.axes.legend()
            self.canvas.draw()
        else:
            self.update_plot()

        self.label_current_step.setText("Current Step: " + step)
        if self.current_step_index < len(self.processing_steps):
            self.label_next_step.setText("Next Step: " + self.processing_steps[self.current_step_index])
        else:
            self.label_next_step.setText("Processing Complete")
        self.update_step_ui()

    def on_next_step(self):
        if self.current_step_index >= len(self.processing_steps):
            QMessageBox.information(self, "Info", "Processing complete.")
            return
        step = self.processing_steps[self.current_step_index]
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
        elif step == 'Polyfit':
            try:
                polyorder = int(self.edit_polyorder.text())
            except ValueError:
                QMessageBox.warning(self, "Error", "Polyorder must be an integer!")
                return
            before = np.copy(self.current_spect)
            base, finalSpect = FluorescenceBackgroundSubtraction(self.current_spect, polyorder)
            self.operations.append(f"FluorescenceBackgroundSubtraction(polyorder={polyorder})")
            self.current_spect = before
            # Check if the user wants a comparison plot

            if self.current_wvn is not None and len(self.current_wvn) == len(before):
                x = self.current_wvn
            else:
                x = np.arange(len(before))
            self.canvas.axes.clear()
            self.canvas.axes.plot(x, before, label="Spectrum", color="blue", linestyle='-')
            self.canvas.axes.plot(x, base, label="Polyfit Line", color="red", linestyle='--')
            self.canvas.axes.set_title("Polyfit Overview")
            self.canvas.axes.legend()
            self.canvas.draw()
        elif step == "FluorescenceBackgroundSubtraction":
            try:
                polyorder = int(self.edit_polyorder.text())
            except ValueError:
                QMessageBox.warning(self, "Error", "Polyorder must be an integer!")
                return
            # Save the current spectrum before processing for comparison
            base, finalSpect = FluorescenceBackgroundSubtraction(self.current_spect, polyorder)
            self.operations.append(f"FluorescenceBackgroundSubtraction(polyorder={polyorder})")
            self.current_spect = finalSpect
        elif step == "Normalization":
            self.current_spect = Normalize(self.current_spect)
            self.operations.append("Normalization")
        else:
            QMessageBox.warning(self, "Error", "Unknown processing step.")
            return

        self.add_history(step)
        self.current_step_index += 1
        if self.current_step_index < len(self.processing_steps):
            self.label_current_step.setText("Current Step: " + self.processing_steps[self.current_step_index - 1])
            self.label_next_step.setText("Next Step: " + self.processing_steps[self.current_step_index])
        else:
            self.label_next_step.setText("Processing Complete")
        # Only call update_plot if the step did not already update the canvas (e.g., FBS step)
        if step != "Polyfit":
            self.update_plot()
        self.update_step_ui()

    def on_save_figure(self):
        try:
            # Prompt for custom filename
            options = QFileDialog.Options()
            filepath, _ = QFileDialog.getSaveFileName(
                self, "Save Figure As", "processed_spectrum.png",
                "PNG Files (*.png);;All Files (*)", options=options
            )
            if not filepath:
                return
            self.canvas.fig.savefig(filepath)
            self.label_saved_file.setText("Saved Figure: " + filepath)
            QMessageBox.information(self, "Saved", f"Figure saved to {filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save figure: {e}")

    def on_save_data(self):
        if self.current_wvn is None or self.current_spect is None:
            QMessageBox.warning(self, "Error", "Empty data, cannot save!")
            return
        try:
            # Prompt user to select directory and filename prefix
            options = QFileDialog.Options()
            base_path, _ = QFileDialog.getSaveFileName(
                self, "Save Spectral Data As", "spectrum_data",
                "CSV Files (*.csv);;All Files (*)", options=options
            )
            if not base_path:
                return
            # Save both Wvn and Spect data
            wvn_filepath = base_path + "_wvn.csv"
            spect_filepath = base_path + "_spect.csv"
            np.savetxt(wvn_filepath, self.current_wvn.reshape(-1, 1), delimiter=",", header="Wavelength", comments='')
            np.savetxt(spect_filepath, self.current_spect.reshape(-1, 1), delimiter=",", header="SpectralIntensity", comments='')
            QMessageBox.information(self, "Saved",
                                    f"Data saved to:\n{wvn_filepath}\n{spect_filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save data: {e}")


    def on_load_rdata_files(self):
        data_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Spectrum Measurement Data",
            "",
            "Data Files (*.txt *.csv *.xlsx);;Text Files (*.txt);;CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)"
        )
        if not data_file:
            return
        wlcorr_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Whitelight Correction Data",
            "",
            "Data Files (*.txt *.csv *.xlsx);;Text Files (*.txt);;CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)"
        )
        if not wlcorr_file:
            return
        wvn_file, _ = QFileDialog.getOpenFileName(self, "Select Calibration File", "",
                                                  "MAT Files (*.mat);;All Files (*)")
        if not wvn_file:
            return

        try:
            # data_df = rdata.read_txt_file(data_file, delimiter=',', header=None)
            # self.current_spect = data_df.iloc[:, 1:].mean(axis=1).to_numpy().astype(np.float64)


            data_df = rdata.load_spectrum_data(data_file)
            self.current_spect = data_df.flatten().astype(np.float64)
            if data_df is None:
                QMessageBox.warning(self, "Error", "Can't read data file")
                return


            print(self.current_spect)


            wl_corr = rdata.read_txt_file(wlcorr_file)
            if wl_corr is None:
                QMessageBox.warning(self, "Error", "Can't read WL Correction file")
                return
            self.wlCorr = wl_corr.to_numpy().astype(np.float64)

            self.wvnFull = rdata.getwvnfrompath(wvn_file).flatten().astype(np.float64)
            self.current_wvn = self.wvnFull.copy()

            # Reset history and operations when loading new data
            self.history = []
            self.history_list.clear()
            self.operations = []
            self.current_step_index = 1

            self.btn_previous.setVisible(True)
            self.btn_next.setVisible(True)
            self.btn_save_data.setVisible(True)
            self.btn_save_fig.setVisible(True)

            self.operations.append("LoadData")
            self.add_history("LoadData")
            self.update_plot()
            QMessageBox.information(self, "Loaded", "Data files loaded successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to read rData files: {e}")

# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = P_Mean_Process_UI()
#     window.show()
#     sys.exit(app.exec_())
