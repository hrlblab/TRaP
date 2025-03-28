
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QApplication, QMainWindow, QGridLayout, QWidget, QLabel, QPushButton, QLineEdit, QCheckBox, \
    QVBoxLayout, QFileDialog, QMessageBox, QHBoxLayout, QComboBox

from UI_utils.UI_Config_Manager import ConfigManagerUI
from UI_utils.UI_P_Mean_Process import P_Mean_Process_UI
from UI_utils.UI_P_Mean_Batch_Process import BatchPMeanUI
from UI_utils.UI_Calibration import WaveformSelectionUI
LOGO_ADDR = 'vanderbilt_biophotonics_center_logo.jpg'


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initMainUI()


    def initMainUI(self):
        self.setWindowTitle("RAMAN Process")
        self.setGeometry(300, 200, 400, 300)

        self.layout = QVBoxLayout()

        # Logo
        self.logoLabel = QLabel(self)
        pixmap = QPixmap(LOGO_ADDR)  # 替换为实验室 Logo 文件的路径
        pixmap = pixmap.scaled(200, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 调整 Logo 大小
        self.logoLabel.setPixmap(pixmap)
        self.logoLabel.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.logoLabel)

        self.buttons = []
        self.titles = ["Config Manager", "Calibration", "Spectrum Process", "Spectrum Batch Process"]
        self.opened_windows = []

        for title in self.titles:
            button = QPushButton(title)
            button.clicked.connect(lambda checked, t=title: self.open_window(t))
            self.layout.addWidget(button)
            self.buttons.append(button)

        self.setLayout(self.layout)

    def open_window(self, title):
        if title == 'Spectrum Process':
            new_window = P_Mean_Process_UI()
        elif title == 'Config Manager':
            new_window = ConfigManagerUI()
        elif title == 'Spectrum Batch Process':
            new_window = BatchPMeanUI()
        elif title == 'Calibration':
            new_window = WaveformSelectionUI()

        self.opened_windows.append(new_window)
        new_window.show()

    def closeEvent(self, a0, QCloseEvent=None):
        for window in self.opened_windows:
            window.close()

        a0.accept()