import sys
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QFileDialog, QMessageBox, QListWidget, QInputDialog, QProgressBar
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.io import savemat

from utils.XAxisCaliibratiion import XAxisCalibration  # 你自己的模块路径


def load_1col_file(filepath):
    ext = filepath.lower().split('.')[-1]
    if ext in ['txt', 'csv']:
        data = np.loadtxt(filepath)
    elif ext in ['xls', 'xlsx']:
        df = pd.read_excel(filepath, header=None)
        data = df.values.squeeze()
    else:
        raise ValueError("Unsupported file format")
    if data.ndim != 1:
        raise ValueError("File must contain one column")
    return data


class WaveformCanvas(FigureCanvas):
    def __init__(self, parent=None, width=7, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.selected_points = []
        self.max_points = 0
        self.data = None
        self.mpl_connect('button_press_event', self.on_click)

    def load_waveform(self, filepath):
        try:
            data = load_1col_file(filepath)
            if data.ndim == 1:
                x = np.arange(len(data))
                y = data
            else:
                x = data[:, 0]
                y = data[:, 1]
            y = (y-min(y)) / (max(y)-min(y))
            self.data = (x, y)
            self.selected_points = []
            self.ax.clear()
            self.ax.plot(x, y)
            self.ax.set_title(f"User-Measured NeAr Spectrum")
            self.ax.legend()
            self.draw()
            self.show()
            QApplication.processEvents()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load waveform:\n{e}")

    def set_max_points(self, max_points):
        self.max_points = max_points

    def on_click(self, event):
        if event.inaxes != self.ax or self.data is None:
            return
        if len(self.selected_points) >= self.max_points:
            QMessageBox.information(self, "Selection", "Maximum number of points selected.")
            return
        x_clicked = int(round(event.xdata))
        y_clicked = event.ydata
        self.selected_points.append((x_clicked, y_clicked))
        self.ax.plot(x_clicked, y_clicked, marker='o', color='red')
        self.draw()


class WaveformSelectionUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spectral Calibration Workflow")
        self.setGeometry(100, 100, 900, 700)

        self.step = 1
        self.lambda_known = False
        self.lambda_value_array = None
        self.waveform1_points = []
        self.waveform2_points = []
        self.neon_spectrum = None
        self.acet_spectrum = None

        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)

        self.label_step = QLabel("Step 1: Upload Neon spectrum")
        self.layout.addWidget(self.label_step)

        self.btn_upload_neon = QPushButton("Upload Neon Spectrum")
        self.btn_upload_neon.clicked.connect(self.upload_neon)
        self.layout.addWidget(self.btn_upload_neon)

        self.input_neon_points = QLineEdit()
        self.input_neon_points.setPlaceholderText("Enter number of Neon peaks to select")
        self.layout.addWidget(self.input_neon_points)

        self.label_current = QLabel("No spectrum loaded")
        self.layout.addWidget(self.label_current)

        self.canvas = WaveformCanvas(self, width=7, height=5, dpi=100)
        self.layout.addWidget(self.canvas)

        self.list_points = QListWidget()
        self.layout.addWidget(self.list_points)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        self.btn_continue = QPushButton("Continue")
        self.btn_continue.clicked.connect(self.next_step)
        self.layout.addWidget(self.btn_continue)

        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self.prev_step)
        self.layout.addWidget(self.btn_back)

        self.btn_process = QPushButton("Process and Save")
        self.btn_process.clicked.connect(self.process_and_save)
        self.btn_process.hide()
        self.layout.addWidget(self.btn_process)

        self.update_step_ui()

    def update_step_ui(self):
        self.btn_upload_neon.hide()
        self.input_neon_points.hide()
        self.canvas.hide()
        self.list_points.hide()
        self.label_current.hide()
        self.progress_bar.setVisible(False)
        self.btn_process.hide()

        if self.step == 1:
            self.btn_upload_neon.show()
            self.input_neon_points.show()
            self.label_step.setText("Step 1: Upload Neon spectrum and enter peak count")
        elif self.step == 2:
            self.canvas.show()
            self.label_current.show()
            self.label_step.setText("Step 2: Select Neon peak points")
        elif self.step == 3:
            self.label_step.setText("Step 3: Do you know the laser wavelength?")
        elif self.step == 3.6:
            self.canvas.show()
            self.label_current.show()
            self.label_step.setText("Step 3a: Select Acet peak points")
        elif self.step == 4:
            self.label_step.setText("Step 4: Ready to calibrate and save")
            self.btn_process.show()
            self.canvas.show()
            self.label_current.show()
            self.btn_continue.setText("Exit")
            self.btn_continue.show()

    def upload_neon(self):
        if self.step != 1:
            return
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Neon Spectrum", "", "Supported Files (*.txt *.csv *.xlsx)")
        if fileName:
            self.canvas.load_waveform(fileName)
            self.neon_spectrum = self.canvas.data[1]
            self.label_current.setText(f"Loaded: {fileName.split('/')[-1]}")
            self.list_points.clear()

    def next_step(self):
        if self.step == 1:
            try:
                max_pts = int(self.input_neon_points.text())
                self.canvas.set_max_points(max_pts)
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Please enter a valid integer for peak number.")
                return
            if not self.canvas.data:
                QMessageBox.warning(self, "Error", "Please upload the Neon spectrum first.")
                return
            self.step = 2
        elif self.step == 2:
            if not self.canvas.selected_points:
                QMessageBox.warning(self, "No Points", "Please select at least one peak.")
                return
            self.waveform1_points = self.canvas.selected_points.copy()
            self.list_points.addItem("Neon selected points:")
            for p in self.waveform1_points:
                self.list_points.addItem(str(p))
            self.step = 3
            self.ask_lambda_known()
        elif self.step == 3.6:
            if not self.canvas.selected_points:
                QMessageBox.warning(self, "No Points", "Please select acet peaks.")
                return
            self.waveform2_points = self.canvas.selected_points.copy()
            self.list_points.addItem("Acet selected points:")
            for p in self.waveform2_points:
                self.list_points.addItem(str(p))
            self.step = 4
        elif self.step == 4 and self.btn_continue.text() == "Exit":
            self.close()
        self.update_step_ui()

    def prev_step(self):
        if self.step > 1:
            self.step -= 1
            self.update_step_ui()

    def ask_lambda_known(self):
        reply = QMessageBox.question(
            self, "Laser Wavelength", "Do you know the EXACT laser wavelength with AT LEAST three decimal places? \nIf not, you will be need to upload an Acetominophen spectrum measurement on your system to approximate it. Note that this approximation is not recommended. Please make sure you understand the implication of this before proceeding.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.lambda_known = True
            self.get_lambda_value()
        else:
            # QMessageBox.warning(
            #     self,
            #     "Warning",
            #     "It is not recommended to estimate laser wavelength from spectra.\n"
            #     "Please make sure you understand the implications before continuing."
            # )
            self.lambda_known = False
            self.step = 3.5
            self.prepare_acet_step()
        self.update_step_ui()

    def get_lambda_value(self):
        while True:
            text, ok = QInputDialog.getText(self, "Laser Wavelength", "Enter known exact laser wavelength (in nm):")
            if not ok:
                return
            try:
                value = float(text)
                if 0 < value < 9999:
                    # Round to 3 decimal places
                    value = round(value, 3)
                    self.lambda_value_array = np.array([value])
                    QMessageBox.information(self, "Wavelength Accepted", f"Lambda = {value:.3f} nm recorded.")
                    self.step = 4
                    self.update_step_ui()
                    return
                else:
                    QMessageBox.warning(self, "Invalid Range", "Please enter a positive wavelength < 9999.")
            except ValueError:
                QMessageBox.warning(self, "Invalid Input",
                                    "Please enter a valid floating point number with 3 decimal places.")

    def get_lambda_file(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Lambda File", "", "Supported Files (*.txt *.csv *.xlsx)")
        if fileName:
            try:
                self.lambda_value_array = load_1col_file(fileName)
                QMessageBox.information(self, "Success", f"{len(self.lambda_value_array)} lambda values loaded.")
                self.step = 4
                self.update_step_ui()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def prepare_acet_step(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Acet Spectrum", "", "Supported Files (*.txt *.csv *.xlsx)")
        if fileName:
            self.canvas.load_waveform(fileName)
            self.acet_spectrum = self.canvas.data[1]
            self.label_current.setText(f"Loaded: {fileName.split('/')[-1]}")
            try:
                pts_str, ok = QInputDialog.getText(self, "Acet Peak Number", "Enter number of acet peaks:")
                if not ok:
                    return
                max_pts = int(pts_str)
                self.canvas.set_max_points(max_pts)
                self.step = 3.6
                self.update_step_ui()
            except ValueError:
                QMessageBox.warning(self, "Format Error", "Please enter a valid number.")

    def process_and_save(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        QApplication.processEvents()

        cal = XAxisCalibration()
        cal.choose_neon_library('neon')
        neon_x = np.array([p[0] for p in self.waveform1_points])
        neon_y = np.array([p[1] for p in self.waveform1_points])

        if self.lambda_known:
            cal.peak_num(near_num=len(neon_x), acet_num=0)
            cal.nearX = np.arange(len(neon_x))
            Wvn = cal.Calibration_without_acetSpec(neon_x, neon_y, self.neon_spectrum, self.lambda_value_array)
        else:
            acet_x = np.array([p[0] for p in self.waveform2_points])
            acet_y = np.array([p[1] for p in self.waveform2_points])
            cal.peak_num(near_num=len(neon_x), acet_num=len(acet_x))
            cal.nearX = np.arange(len(neon_x))
            cal.acetX = np.arange(len(acet_x))
            Wvn = cal.Calibration_with_acetSpec(neon_x, neon_y, self.neon_spectrum, acet_x, acet_y, self.acet_spectrum)
        Wvn = Wvn.reshape(1, -1).T
        print(Wvn.size)

        self.progress_bar.setValue(80)
        QApplication.processEvents()

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Calibrated Result", "", "MAT files (*.mat)")
        if save_path:
            if not save_path.endswith(".mat"):
                save_path += ".mat"
            savemat(save_path, {'Cal': {'Wvn': Wvn}})
            self.progress_bar.setValue(100)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WaveformSelectionUI()
    window.show()
    sys.exit(app.exec_())
