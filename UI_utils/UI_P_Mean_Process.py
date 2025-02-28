import fnmatch
import json
import sys
import os
from datetime import datetime

from utils.io import rdata, wdata
import numpy as np
import pandas as pd  # 确保导入 pandas
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
                             QLineEdit, QCheckBox, QVBoxLayout, QFileDialog, QMessageBox,
                             QHBoxLayout, QComboBox)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.SpectralPreprocess import (Binning, Denoise, Truncate, CosmicRayRemoval,
                                      SpectralResponseCorrection, subtractBaseline,
                                      FluorescenceBackgroundSubtraction)




class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.plotted_lines = []

    def plot(self, data):
        self.axes.clear()
        # 如果传入的是 (x, y) 数据则绘制 x-y 曲线，否则绘制 y 曲线
        if isinstance(data, tuple) and len(data) == 2:
            x, y = data
            self.axes.plot(x, y)
        else:
            self.axes.plot(data)
        self.axes.set_title('Data Plots')
        self.draw()

    def draw_lines(self, positions, colors):
        # 清除之前绘制的直线
        for line in self.plotted_lines:
            line.remove()
        self.plotted_lines.clear()
        # 绘制新的直线，并保存引用
        for pos, color in zip(positions, colors):
            line = self.axes.axhline(y=pos, color=color, linewidth=1)
            self.plotted_lines.append(line)
        self.draw()


class P_Mean_Process_UI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spectrum Data Process")
        self.setGeometry(100, 100, 900, 600)

        # 初始数据：模拟波长与光谱数据
        self.wvnFull = np.linspace(400, 900, 500)  # 波长从400到900
        self.rawSpect = np.sin(self.wvnFull / 100) + np.random.normal(0, 0.1, self.wvnFull.shape)
        self.current_spect = self.rawSpect.copy()
        self.current_wvn = self.wvnFull.copy()

        # 为光谱响应校正准备一个 dummy 数组（二维，shape=(500,1)）
        self.wlCorr = np.ones((500, 1)) * 1.2

        # 用于记录处理步骤的列表（后续保存时将包含在文件名中）
        self.operations = []

        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # PlotCanvas 实例
        self.canvas = PlotCanvas(self, width=7, height=5, dpi=100)
        layout.addWidget(self.canvas)
        self.update_plot()  # 初始绘制

        # 参数输入区域（Start, Stop, Polyorder）
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

        # 显示当前保存文件名的 Label
        self.label_saved_file = QLabel("Current File Saved: None")
        layout.addWidget(self.label_saved_file)

        # 按钮区域
        btn_layout = QHBoxLayout()
        layout.addLayout(btn_layout)

        btn_subtract = QPushButton("Subtract Baseline")
        btn_subtract.clicked.connect(self.on_subtract_baseline)
        btn_layout.addWidget(btn_subtract)

        btn_response = QPushButton("Spectral Response Correction")
        btn_response.clicked.connect(self.on_spectral_response_correction)
        btn_layout.addWidget(btn_response)

        btn_cosmic = QPushButton("Cosmic Ray Removal")
        btn_cosmic.clicked.connect(self.on_cosmic_ray_removal)
        btn_layout.addWidget(btn_cosmic)

        btn_truncate = QPushButton("Truncate")
        btn_truncate.clicked.connect(self.on_truncate)
        btn_layout.addWidget(btn_truncate)

        btn_binning = QPushButton("Binning")
        btn_binning.clicked.connect(self.on_binning)
        btn_layout.addWidget(btn_binning)

        btn_denoise = QPushButton("Denoise")
        btn_denoise.clicked.connect(self.on_denoise)
        btn_layout.addWidget(btn_denoise)

        btn_FluorBackSub = QPushButton("FluorescenceBackgroundSubtraction")
        btn_FluorBackSub.clicked.connect(self.on_FluorescenceBackgroundSubtraction)
        btn_layout.addWidget(btn_FluorBackSub)

        btn_save_fig = QPushButton("Save Figure")
        btn_save_fig.clicked.connect(self.on_save_figure)
        btn_layout.addWidget(btn_save_fig)

        btn_save_data = QPushButton("Save Data")
        btn_save_data.clicked.connect(self.on_save_data)
        btn_layout.addWidget(btn_save_data)

        btn_load_rdata = QPushButton("Load Data Files")
        btn_load_rdata.clicked.connect(self.on_load_rdata_files)
        btn_layout.addWidget(btn_load_rdata)

    def update_plot(self):
        """更新图像显示。若有波长数据，则绘制 x-y 曲线；否则绘制 y 曲线"""
        if self.current_wvn is not None and len(self.current_wvn) == len(self.current_spect):
            self.canvas.plot((self.current_wvn, self.current_spect))
        else:
            self.canvas.plot(self.current_spect)
        # print('spect: ' + f'{self.current_spect.shape}')
        # print('wvn: ' + f'{self.current_wvn.shape}')


    # ----------- 各处理按钮的槽函数 -----------
    def on_subtract_baseline(self):
        self.current_spect = subtractBaseline(self.current_spect)
        self.operations.append("SubtractBaseline")
        self.update_plot()

    def on_spectral_response_correction(self):
        self.current_spect = SpectralResponseCorrection(self.wlCorr, self.current_spect)
        self.operations.append("SpectralResponseCorrection")
        self.update_plot()

    def on_cosmic_ray_removal(self):
        self.current_spect = CosmicRayRemoval(self.current_spect)
        self.operations.append("CosmicRayRemoval")
        self.update_plot()

    def on_truncate(self):
        try:
            start = float(self.edit_start.text())
            stop = float(self.edit_stop.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Start and Stop Must be Number!")
            return
        self.current_wvn, self.current_spect = Truncate(start, stop, self.wvnFull, self.current_spect)
        self.operations.append(f"Truncate({start}-{stop})")
        self.update_plot()

    def on_binning(self):
        if self.current_wvn.size == 0:
            QMessageBox.warning(self, "Warning", "NoneType Input!")
            return
        start = self.current_wvn[0]
        stop = self.current_wvn[-1]
        binned_spect, new_wvn = Binning(start, stop, self.current_wvn, self.current_spect, binwidth=3.5)
        self.current_spect = binned_spect
        self.current_wvn = new_wvn
        self.operations.append("Binning")
        self.update_plot()

    def on_denoise(self):
        self.current_spect = Denoise(self.current_spect, SGorder=2, SGframe=7)
        self.operations.append("Denoise")
        self.update_plot()

    def on_FluorescenceBackgroundSubtraction(self):
        try:
            polyorder = int(self.edit_polyorder.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Polyorder Must be Integer!")
            return
        base, finalSpect = FluorescenceBackgroundSubtraction(self.current_spect, polyorder)
        self.current_spect = finalSpect
        self.operations.append(f"FluorescenceBackgroundSubtraction(polyorder={polyorder})")
        self.update_plot()

    def on_save_figure(self):
        # 调用 wdata 模块保存图像，文件名中记录当前所有操作步骤
        try:
            filepath = wdata.save_figure(self.canvas.fig, self.operations, base_dir=".", file_ext="png")
            self.label_saved_file.setText("Saved Figure: " + filepath)
            QMessageBox.information(self, "Saved", f"Figure saved to {filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save figure: {e}")

    def on_save_data(self):
        if self.current_wvn is None or self.current_spect is None:
            QMessageBox.warning(self, "Error", "Empty Data, Saving Error!")
            return
        try:
            # 对于分开保存，可以分别调用 wdata.save_data 保存不同数据
            wvn_filepath = wdata.save_data(self.current_wvn.reshape(-1, 1), 'Wvn', self.operations,
                                           base_dir=".", file_ext="csv", header=None)
            spect_filepath = wdata.save_data(self.current_spect.reshape(-1, 1), 'Spect', self.operations,
                                             base_dir=".", file_ext="csv", header=None)
            print("Returned data filepaths:", wvn_filepath, spect_filepath)
            QMessageBox.information(self, "Saved",
                                    f"Data saved to:\n{wvn_filepath}\n{spect_filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save data: {e}")

    def on_load_rdata_files(self):
        """
        加载 rData 文件：
          1. Lipid FP 数据（文本文件），使用 utils.io.rdata.read_txt_file 读取，
             并取其第二列开始数据求均值作为 spectrum；
          2. WL Correction 数据，使用 read_txt_file 或 getwlcorrfrompath 读取；
          3. Calibration 数据（MAT 文件），使用 getwvnfrompath 读取。
        """
        # 选择 Lipid FP 数据文件
        data_file, _ = QFileDialog.getOpenFileName(self, "Select Lipid FP Data", "",
                                                   "Text Files (*.txt);;All Files (*)")
        if not data_file:
            return
        # 选择 WL Correction 数据文件
        wlcorr_file, _ = QFileDialog.getOpenFileName(self, "Select WL Correction Data", "",
                                                     "Text Files (*.txt);;All Files (*)")
        if not wlcorr_file:
            return
        # 选择 Calibration 文件（MAT 文件）
        wvn_file, _ = QFileDialog.getOpenFileName(self, "Select Calibration File", "",
                                                  "MAT Files (*.mat);;All Files (*)")
        if not wvn_file:
            return

        try:
            # 使用 read_txt_file 读取 Lipid FP 数据文件
            data_df = rdata.read_txt_file(data_file, delimiter=',', header=None)
            if data_df is None:
                QMessageBox.warning(self, "Error", "Can't Read Data")
                return
            if data_df.shape[1] < 2:
                QMessageBox.warning(self, "Error", "Error format, Col Must Be 2.")
                return
            # 取第二列以后数据的均值作为 spectrum
            self.current_spect = data_df.iloc[:, 1:].mean(axis=1).to_numpy().astype(np.float64)

            # 读取 WL Correction 文件（返回 DataFrame），转换为 numpy 数组
            wl_corr = rdata.read_txt_file(wlcorr_file)
            if wl_corr is None:
                QMessageBox.warning(self, "Error", "Can't Read WL file")
                return
            self.wlCorr = wl_corr.to_numpy().astype(np.float64)

            # 读取 Calibration 文件，获取波长数据
            self.wvnFull = rdata.getwvnfrompath(wvn_file).flatten().astype(np.float64)
            self.current_wvn = self.wvnFull.copy()

            self.operations.append("LoadData")
            self.update_plot()
            QMessageBox.information(self, "Loaded", "Data loaded successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Reading Data Failed: {e}")


