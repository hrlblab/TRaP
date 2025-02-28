import fnmatch
import json
import sys
import os
from datetime import datetime

import numpy as np
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QApplication, QMainWindow, QGridLayout, QWidget, QLabel, QPushButton, QLineEdit, QCheckBox, \
    QVBoxLayout, QFileDialog, QMessageBox, QHBoxLayout, QComboBox

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from UI_utils.UI_System_Select import MainWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())