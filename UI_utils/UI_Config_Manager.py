import json
import os

from PyQt5.QtWidgets import QApplication, QMainWindow, QGridLayout, QWidget, QLabel, QPushButton, QLineEdit, QCheckBox, \
    QVBoxLayout, QFileDialog, QMessageBox, QHBoxLayout, QComboBox
from PyQt5.QtCore import pyqtSignal

class ConfigManager:
    _instance = None
    CONFIG_FILE = "config.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            # ***Config Parameters Here***
            cls._instance.params = {
                "Name": "",
                "System": "Cart",
                "Exc Wavelength": "",  # 使用固定选项，故设为字符串
                "Detector": "",
                "Probe": "Microscope",  # 默认选项
                "Spectrograph Name": "",
                "CCD X": 0.0,
                "CCD Y": 0.0,
                "Raman Shift Range": "Fingerprint",  # 默认选项
                "X-axis Calibration": False,  # False 表示 "N"，True 表示 "Y"
            }
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        """ 从 JSON 文件中加载配置 """
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.params.update(json.load(f))

            except Exception as e:
                print(f"Failed to load config: {e}")

    def save_config(self):
        """ 根据 Name 字段保存到 JSON 文件 """
        name_value = self.params["Name"].strip()
        # 过滤非法字符，确保文件名安全
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name_value)
        file_name = f"{safe_name}.json" if safe_name else "config.json"
        try:
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(self.params, f, ensure_ascii=False, indent=4)
            print(f"✅ Success: {file_name}")
        except Exception as e:
            print(f"❌ Failed to save: {e}")


class ConfigManagerUI(QWidget):
    config_updated = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()  # **Config Manager**
        self.labels = {}
        self.inputs = {}

        # 定义各系统对应的波长和探测器选项及组合关系（可根据需求调整）
        self.system_options = {
            "Cart": {
                "wavelengths": ["785", "680", "830", "730"],
                "detectors": {
                    "785": ["256br", "400br", "Blaze"],
                    "680": ["256br", "400br", "Blaze"],
                    "830": ["Blaze", "Kaiser"],
                    "730": ["Blaze"]
                }
            },
            "Renishaw": {
                "wavelengths": ["785", "633"],
            },
            "Portable": {
                "wavelengths": ["750", "730"],
                # portable系统不需要 Detector 参数，此处不设置 detectors 键
            },
            "MANTIS": {
                "wavelengths": ["830"],
                "detectors": {
                    "830": ["400br", "blaze"]
                }
            }
        }

        self.initUI()

    def initUI(self):
        self.setWindowTitle("Configuration")
        self.setGeometry(400, 200, 300, 500)
        self.layout = QVBoxLayout()

        # 创建“System”下拉框
        system_label = QLabel("System", self)
        self.layout.addWidget(system_label)
        system_combo = QComboBox(self)
        system_combo.addItems(list(self.system_options.keys()))
        index = system_combo.findText(self.config.params["System"])
        if index >= 0:
            system_combo.setCurrentIndex(index)
        self.layout.addWidget(system_combo)
        self.labels["System"] = system_label
        self.inputs["System"] = system_combo

        # 创建“Exc Wavelength”下拉框（选项由 System 决定）
        wl_label = QLabel("Exc Wavelength", self)
        self.layout.addWidget(wl_label)
        wl_combo = QComboBox(self)
        self.layout.addWidget(wl_combo)
        self.labels["Exc Wavelength"] = wl_label
        self.inputs["Exc Wavelength"] = wl_combo

        # 创建“Detector”下拉框（选项由波长决定，如果系统不需要则隐藏）
        det_label = QLabel("Detector", self)
        self.layout.addWidget(det_label)
        det_combo = QComboBox(self)
        self.layout.addWidget(det_combo)
        self.labels["Detector"] = det_label
        self.inputs["Detector"] = det_combo

        # 其他参数：Name、Probe、Spectrograph Name、CCD X、CCD Y、Raman Shift Range、X-axis Calibration
        for param, value in self.config.params.items():
            if param in ["System", "Exc Wavelength", "Detector"]:
                continue
            label = QLabel(param, self)
            self.layout.addWidget(label)
            if param == "Probe":
                combo = QComboBox(self)
                combo.addItems(["Microscope", "Handheld", "Lensed", "SORS", "Classic"])
                index = combo.findText(value)
                if index >= 0:
                    combo.setCurrentIndex(index)
                input_field = combo
            elif param == "Raman Shift Range":
                combo = QComboBox(self)
                combo.addItems(["Fingerprint", "High WVN", "Full Range", "Custom"])
                index = combo.findText(value)
                if index >= 0:
                    combo.setCurrentIndex(index)
                input_field = combo
            elif param == "X-axis Calibration":
                combo = QComboBox(self)
                combo.addItems(["Y", "N"])
                current_val = "Y" if value else "N"
                index = combo.findText(current_val)
                if index >= 0:
                    combo.setCurrentIndex(index)
                input_field = combo
            else:
                input_field = QLineEdit(self)
                input_field.setText(str(value))
            self.layout.addWidget(input_field)
            self.labels[param] = label
            self.inputs[param] = input_field

        # 连接信号：当 System 或 Exc Wavelength 改变时，更新下一级选项
        system_combo.currentIndexChanged.connect(self.update_wavelength_options)
        wl_combo.currentIndexChanged.connect(self.update_detector_options)

        # 根据当前 System 初始化下拉框选项
        self.update_wavelength_options()

        # 保存与加载按钮
        self.save_button = QPushButton("Save", self)
        self.save_button.clicked.connect(self.save_config)
        self.layout.addWidget(self.save_button)

        self.load_button = QPushButton("Load", self)
        self.load_button.clicked.connect(self.load_config_with_dialog)
        self.layout.addWidget(self.load_button)

        self.setLayout(self.layout)

    def update_wavelength_options(self):
        system = self.inputs["System"].currentText()
        wavelengths = self.system_options.get(system, {}).get("wavelengths", [])
        wl_combo = self.inputs["Exc Wavelength"]
        wl_combo.clear()
        wl_combo.addItems(wavelengths)
        # 如果之前保存的波长存在于新选项中，则选择之；否则默认选中第一个
        current_wl = self.config.params.get("Exc Wavelength", "")
        if current_wl in wavelengths:
            index = wl_combo.findText(current_wl)
            wl_combo.setCurrentIndex(index)
        else:
            wl_combo.setCurrentIndex(0)
        # 同步更新 Detector 选项
        self.update_detector_options()

    def update_detector_options(self):
        system = self.inputs["System"].currentText()
        # 如果该系统不需要 Detector 参数，则隐藏对应控件
        if system in ["Portable", "Renishaw"]:
            self.labels["Detector"].setVisible(False)
            self.inputs["Detector"].setVisible(False)
            # 保存时将 Detector 参数清空
            self.config.params["Detector"] = ""
        else:
            self.labels["Detector"].setVisible(True)
            self.inputs["Detector"].setVisible(True)
            wavelength = self.inputs["Exc Wavelength"].currentText()
            detectors = self.system_options.get(system, {}).get("detectors", {}).get(wavelength, [])
            det_combo = self.inputs["Detector"]
            det_combo.clear()
            det_combo.addItems(detectors)
            # 如果之前保存的 Detector 存在，则选中之；否则默认选中第一个
            current_det = self.config.params.get("Detector", "")
            if current_det in detectors:
                index = det_combo.findText(current_det)
                det_combo.setCurrentIndex(index)
            else:
                det_combo.setCurrentIndex(0)

    def save_config(self):
        # Update dynamic combo box values first
        self.config.params["System"] = self.inputs["System"].currentText()
        self.config.params["Exc Wavelength"] = self.inputs["Exc Wavelength"].currentText()

        # Update Detector if visible
        if self.inputs["Detector"].isVisible():
            self.config.params["Detector"] = self.inputs["Detector"].currentText()
        else:
            self.config.params["Detector"] = ""

        # Update other parameters
        for param, input_field in self.inputs.items():
            if param in ["System", "Exc Wavelength", "Detector"]:
                continue
            if isinstance(input_field, QComboBox):
                selected = input_field.currentText()
                if param == "X-axis Calibration":
                    self.config.params[param] = (selected == "Y")
                else:
                    self.config.params[param] = selected
            elif isinstance(input_field, QCheckBox):
                self.config.params[param] = input_field.isChecked()
            else:
                text = input_field.text().strip()
                if param in ["CCD X", "CCD Y"]:
                    try:
                        self.config.params[param] = float(text)
                    except ValueError:
                        QMessageBox.warning(self, "TypeError", f"Parameter {param} requires a numeric value.")
                        return
                else:
                    self.config.params[param] = text

        # Use file dialog to let user choose save path
        name_value = self.config.params["Name"].strip()
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name_value)
        default_filename = f"{safe_name}.json" if safe_name else "config.json"

        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Config File", default_filename,
                                                   "JSON Files (*.json);;All Files (*)", options=options)
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    json.dump(self.config.params, f, ensure_ascii=False, indent=4)
                QMessageBox.information(self, "Success", f"Configuration saved to {file_name}")
                self.config_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", f"Failed to save configuration:\n{e}")
        else:
            QMessageBox.information(self, "Canceled", "Save operation was canceled.")

    def load_config_with_dialog(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Choose Config File", "",
                                                   "JSON Files (*.json);;All Files (*)", options=options)
        if file_name:
            self.config.CONFIG_FILE = file_name
            self.config.load_config()
            self.config_updated.emit()
            # 更新 UI 中的各个控件
            for param, input_field in self.inputs.items():
                if isinstance(input_field, QComboBox):
                    if param == "X-axis Calibration":
                        current_val = "Y" if self.config.params[param] else "N"
                        index = input_field.findText(current_val)
                        if index >= 0:
                            input_field.setCurrentIndex(index)
                    elif param in ["System", "Exc Wavelength", "Detector"]:
                        # 动态更新部分由 update_wavelength_options() 与 update_detector_options() 处理
                        continue
                    else:
                        index = input_field.findText(str(self.config.params[param]))
                        if index >= 0:
                            input_field.setCurrentIndex(index)
                elif isinstance(input_field, QCheckBox):
                    input_field.setChecked(self.config.params[param])
                else:
                    input_field.setText(str(self.config.params[param]))
            # 更新动态下拉框的选项
            self.update_wavelength_options()


