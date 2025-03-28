import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
                             QLineEdit, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox,
                             QListWidget)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class WaveformCanvas(FigureCanvas):
    def __init__(self, parent=None, width=7, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)  # Create a Figure object
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.selected_points = []  # Stores selected points as (index, value)
        self.max_points = 0        # Maximum allowed points to select
        self.data = None           # (x, y) data tuple
        self.mpl_connect('button_press_event', self.on_click)

    def load_waveform(self, filepath):
        try:
            data = np.loadtxt(filepath)
            if data.ndim == 1:
                x = np.arange(len(data))
                y = data
            else:
                # If two columns exist, use the first column as x and second as y.
                x = data[:, 0]
                y = data[:, 1]
            self.data = (x, y)
            self.selected_points = []  # Clear previously selected points
            self.ax.clear()
            self.ax.plot(x, y, label="Waveform")
            self.ax.set_title("Waveform Plot")
            self.ax.legend()
            self.draw()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load waveform:\n{e}")

    def set_max_points(self, max_points):
        self.max_points = max_points

    def on_click(self, event):
        # If click is not inside the axes or no data is loaded, ignore.
        if event.inaxes != self.ax or self.data is None:
            return
        if len(self.selected_points) >= self.max_points:
            QMessageBox.information(self, "Selection", "Maximum number of points selected.")
            return
        # For 1D data, x-axis is the index; round event.xdata to nearest integer.
        x_clicked = int(round(event.xdata))
        y_clicked = event.ydata
        self.selected_points.append((x_clicked, y_clicked))
        # Plot the selected point as a red circle.
        self.ax.plot(x_clicked, y_clicked, marker='o', color='red')
        self.draw()

class WaveformSelectionUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Waveform Point Selection")
        self.setGeometry(100, 100, 800, 600)
        # Stores selected points for each waveform.
        self.waveform1_points = []
        self.waveform2_points = []
        self.current_waveform = None  # 1 for waveform1, 2 for waveform2.
        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Two input boxes for setting max points for each waveform.
        max_layout = QHBoxLayout()
        self.label_max_wf1 = QLabel("Max Points for Waveform 1:")
        max_layout.addWidget(self.label_max_wf1)
        self.edit_max_wf1 = QLineEdit("5")
        max_layout.addWidget(self.edit_max_wf1)
        self.label_max_wf2 = QLabel("Max Points for Waveform 2:")
        max_layout.addWidget(self.label_max_wf2)
        self.edit_max_wf2 = QLineEdit("5")
        max_layout.addWidget(self.edit_max_wf2)
        main_layout.addLayout(max_layout)

        # Buttons to load Waveform 1 and Waveform 2
        btn_layout = QHBoxLayout()
        self.btn_load_wf1 = QPushButton("Load Waveform 1")
        self.btn_load_wf1.clicked.connect(self.load_waveform1)
        btn_layout.addWidget(self.btn_load_wf1)
        self.btn_load_wf2 = QPushButton("Load Waveform 2")
        self.btn_load_wf2.clicked.connect(self.load_waveform2)
        btn_layout.addWidget(self.btn_load_wf2)
        main_layout.addLayout(btn_layout)

        # Label to show which waveform is currently loaded.
        self.label_current = QLabel("No waveform loaded")
        main_layout.addWidget(self.label_current)

        # Matplotlib canvas for displaying the waveform.
        self.canvas = WaveformCanvas(self, width=7, height=5, dpi=100)
        main_layout.addWidget(self.canvas)

        # List widget to display the selected points.
        self.list_points = QListWidget()
        main_layout.addWidget(self.list_points)

        # Action buttons: Clear, Record, and Next Step Processing.
        action_layout = QHBoxLayout()
        self.btn_clear = QPushButton("Clear Selections")
        self.btn_clear.clicked.connect(self.clear_selections)
        action_layout.addWidget(self.btn_clear)
        self.btn_record = QPushButton("Record Selections")
        self.btn_record.clicked.connect(self.record_selections)
        action_layout.addWidget(self.btn_record)
        self.btn_next = QPushButton("Next Step Processing")
        self.btn_next.clicked.connect(self.next_step_processing)
        action_layout.addWidget(self.btn_next)
        main_layout.addLayout(action_layout)

    def set_max_points_for_current_waveform(self):
        try:
            if self.current_waveform == 1:
                max_points = int(self.edit_max_wf1.text())
            elif self.current_waveform == 2:
                max_points = int(self.edit_max_wf2.text())
            else:
                return
            self.canvas.set_max_points(max_points)
        except ValueError:
            QMessageBox.warning(self, "Error", "Max points must be an integer.")

    def load_waveform1(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Load Waveform 1", "", "Text Files (*.txt);;All Files (*)")
        if fileName:
            self.canvas.load_waveform(fileName)
            self.current_waveform = 1
            self.label_current.setText("Current Waveform: 1")
            self.set_max_points_for_current_waveform()
            self.list_points.clear()

    def load_waveform2(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Load Waveform 2", "", "Text Files (*.txt);;All Files (*)")
        if fileName:
            self.canvas.load_waveform(fileName)
            self.current_waveform = 2
            self.label_current.setText("Current Waveform: 2")
            self.set_max_points_for_current_waveform()
            self.list_points.clear()

    def clear_selections(self):
        self.canvas.selected_points = []
        if self.canvas.data is not None:
            x, y = self.canvas.data
            self.canvas.ax.clear()
            self.canvas.ax.plot(x, y, label="Waveform")
            self.canvas.ax.set_title("Waveform Plot")
            self.canvas.ax.legend()
            self.canvas.draw()
        self.list_points.clear()

    def record_selections(self):
        pts = self.canvas.selected_points.copy()
        if self.current_waveform == 1:
            self.waveform1_points = pts
            self.list_points.addItem("Waveform 1 Selected Points:")
            for p in pts:
                self.list_points.addItem(str(p))
        elif self.current_waveform == 2:
            self.waveform2_points = pts
            self.list_points.addItem("Waveform 2 Selected Points:")
            for p in pts:
                self.list_points.addItem(str(p))
        else:
            QMessageBox.warning(self, "Error", "No waveform loaded.")

    def next_step_processing(self):
        if not self.waveform1_points or not self.waveform2_points:
            QMessageBox.warning(self, "Error", "Please record points for both waveforms first!")
            return
        msg = f"Waveform 1 Selected Points:\n{self.waveform1_points}\n\nWaveform 2 Selected Points:\n{self.waveform2_points}"
        QMessageBox.information(self, "Next Step Processing", msg)
        # You can expand the data processing logic here.

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WaveformSelectionUI()
    window.show()
    sys.exit(app.exec_())
