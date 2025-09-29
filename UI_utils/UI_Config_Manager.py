import json
import os

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QLineEdit, \
    QVBoxLayout, QFileDialog, QMessageBox, QComboBox
from PyQt5.QtCore import pyqtSignal

class ConfigManager:
    _instance = None
    CONFIG_FILE = "config.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.params = {
                "Name": "",
                "System": "Cart",
                "Exc Wavelength": "",
                "Detector": "",
                "Probe": "Microscope",
                "Spectrograph Name": "",
                "CCD X": 0.0,
                "CCD Y": 0.0,
                "Raman Shift Range": "Fingerprint",
            }
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        """Load config JSON into self.params."""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.params.update(json.load(f))
            except Exception as e:
                print(f"Failed to load config: {e}")

    def save_config(self):
        """Save params to JSON file named by 'Name'."""
        name_value = self.params["Name"].strip()
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
        self.config = ConfigManager()
        self.labels = {}
        self.inputs = {}

        # System → wavelength/detector mapping
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
            "Renishaw": {"wavelengths": ["785", "633"]},
            "Portable": {"wavelengths": ["750", "730"]},
            "MANTIS": {
                "wavelengths": ["830"],
                "detectors": {"830": ["400br", "blaze"]}
            }
        }

        self.initUI()

    def initUI(self):
        self.setWindowTitle("Configuration")
        self.setGeometry(400, 200, 300, 520)
        self.layout = QVBoxLayout()

        # System
        system_label = QLabel("System", self)
        self.layout.addWidget(system_label)
        system_combo = QComboBox(self)
        system_combo.addItems(list(self.system_options.keys()))
        idx = system_combo.findText(self.config.params.get("System", "Cart"))
        if idx >= 0:
            system_combo.setCurrentIndex(idx)
        self.layout.addWidget(system_combo)
        self.labels["System"] = system_label
        self.inputs["System"] = system_combo

        # Exc Wavelength
        wl_label = QLabel("Exc Wavelength", self)
        self.layout.addWidget(wl_label)
        wl_combo = QComboBox(self)
        self.layout.addWidget(wl_combo)
        self.labels["Exc Wavelength"] = wl_label
        self.inputs["Exc Wavelength"] = wl_combo

        # Detector
        det_label = QLabel("Detector", self)
        self.layout.addWidget(det_label)
        det_combo = QComboBox(self)
        self.layout.addWidget(det_combo)
        self.labels["Detector"] = det_label
        self.inputs["Detector"] = det_combo

        # Other fields
        for param in ["Name", "Probe", "Spectrograph Name", "CCD X", "CCD Y", "Raman Shift Range"]:
            label = QLabel(param, self)
            self.layout.addWidget(label)

            if param == "Probe":
                combo = QComboBox(self)
                combo.addItems(["Microscope", "Handheld", "Lensed", "SORS", "Classic"])
                idx = combo.findText(self.config.params.get(param, "Microscope"))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                input_field = combo

            elif param == "Raman Shift Range":
                combo = QComboBox(self)
                combo.addItems(["Fingerprint", "High WVN", "Full Range", "Custom"])
                idx = combo.findText(self.config.params.get(param, "Fingerprint"))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                input_field = combo

            else:
                le = QLineEdit(self)
                le.setText(str(self.config.params.get(param, "")))
                input_field = le

            self.layout.addWidget(input_field)
            self.labels[param] = label
            self.inputs[param] = input_field

        # wiring
        system_combo.currentIndexChanged.connect(self.update_wavelength_options)
        wl_combo.currentIndexChanged.connect(self.update_detector_options)
        self.update_wavelength_options()

        # Save / Load
        btn_save = QPushButton("Save", self)
        btn_save.clicked.connect(self.save_config)
        self.layout.addWidget(btn_save)

        btn_load = QPushButton("Load", self)
        btn_load.clicked.connect(self.load_config_with_dialog)
        self.layout.addWidget(btn_load)

        self.setLayout(self.layout)

    def update_wavelength_options(self):
        system = self.inputs["System"].currentText()
        wavelengths = self.system_options.get(system, {}).get("wavelengths", [])
        wl_combo = self.inputs["Exc Wavelength"]
        wl_combo.clear()
        wl_combo.addItems(wavelengths)
        current_wl = self.config.params.get("Exc Wavelength", "")
        if current_wl in wavelengths:
            wl_combo.setCurrentIndex(wl_combo.findText(current_wl))
        else:
            wl_combo.setCurrentIndex(0)
        self.update_detector_options()

    def update_detector_options(self):
        system = self.inputs["System"].currentText()
        det_combo = self.inputs["Detector"]
        if system in ["Portable", "Renishaw"]:
            self.labels["Detector"].setVisible(False)
            det_combo.setVisible(False)
            self.config.params["Detector"] = ""
        else:
            self.labels["Detector"].setVisible(True)
            det_combo.setVisible(True)
            wavelength = self.inputs["Exc Wavelength"].currentText()
            detectors = self.system_options.get(system, {}).get("detectors", {}).get(wavelength, [])
            det_combo.clear()
            det_combo.addItems(detectors)
            current_det = self.config.params.get("Detector", "")
            if current_det in detectors:
                det_combo.setCurrentIndex(det_combo.findText(current_det))
            else:
                if detectors:
                    det_combo.setCurrentIndex(0)

    def _collect_to_params(self):
        """Collect UI to params."""
        self.config.params["System"] = self.inputs["System"].currentText()
        self.config.params["Exc Wavelength"] = self.inputs["Exc Wavelength"].currentText()
        self.config.params["Detector"] = self.inputs["Detector"].currentText() if self.inputs["Detector"].isVisible() else ""

        for param, input_field in self.inputs.items():
            if param in ["System", "Exc Wavelength", "Detector"]:
                continue
            if isinstance(input_field, QComboBox):
                self.config.params[param] = input_field.currentText()
            else:
                text = input_field.text().strip()
                if param in ["CCD X", "CCD Y"]:
                    try:
                        self.config.params[param] = float(text)
                    except ValueError:
                        QMessageBox.warning(self, "TypeError", f"{param} must be numeric.")
                        return False
                else:
                    self.config.params[param] = text
        return True

    def save_config(self):
        if not self._collect_to_params():
            return
        name_value = self.config.params.get("Name", "").strip()
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name_value)
        default_filename = f"{safe_name}.json" if safe_name else "config.json"

        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Config File", default_filename,
                                                   "JSON Files (*.json);;All Files (*)", options=options)
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    json.dump(self.config.params, f, ensure_ascii=False, indent=4)
                self.config.CONFIG_FILE = file_name
                QMessageBox.information(self, "Success", f"Configuration saved to {file_name}")
                self.config_updated.emit()
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", f"Failed to save:\n{e}")
        else:
            QMessageBox.information(self, "Canceled", "Save canceled.")

    def load_config_with_dialog(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Choose Config File", "",
                                                   "JSON Files (*.json);;All Files (*)", options=options)
        if file_name:
            try:
                self.config.CONFIG_FILE = file_name
                self.config.load_config()
                # refresh UI
                for param, input_field in self.inputs.items():
                    if isinstance(input_field, QComboBox):
                        if param in ["System", "Exc Wavelength", "Detector"]:
                            # postpone to update_*()
                            continue
                        idx = input_field.findText(str(self.config.params.get(param, "")))
                        if idx >= 0:
                            input_field.setCurrentIndex(idx)
                    else:
                        input_field.setText(str(self.config.params.get(param, "")))

                # Update chaining combos
                sys_idx = self.inputs["System"].findText(self.config.params.get("System", "Cart"))
                if sys_idx >= 0:
                    self.inputs["System"].setCurrentIndex(sys_idx)
                self.update_wavelength_options()
                wl_idx = self.inputs["Exc Wavelength"].findText(self.config.params.get("Exc Wavelength", ""))
                if wl_idx >= 0:
                    self.inputs["Exc Wavelength"].setCurrentIndex(wl_idx)
                self.update_detector_options()
                det_name = self.config.params.get("Detector", "")
                if det_name and self.inputs["Detector"].isVisible():
                    det_idx = self.inputs["Detector"].findText(det_name)
                    if det_idx >= 0:
                        self.inputs["Detector"].setCurrentIndex(det_idx)

                QMessageBox.information(self, "Loaded", f"Configuration loaded from {file_name}")
                self.config_updated.emit()
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "Load Failed", f"Failed to load:\n{e}")
