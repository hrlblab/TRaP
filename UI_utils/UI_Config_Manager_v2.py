# UI_Config_Manager_v2.py
# -*- coding: utf-8 -*-

"""
Configuration Manager v2 - Optimized version

Features:
  - Grouped layout with clear sections
  - Recent configurations list
  - Quick save/load functionality
  - Auto-save to default location
  - Signal emission for config updates
  - Summary string for display in wizard

All UI text and comments in English.
"""

import json
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QDialog, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QComboBox,
    QGroupBox, QGridLayout, QListWidget, QListWidgetItem, QFrame,
    QSplitter, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont


# Default config directory
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs")
RECENT_FILE = os.path.join(CONFIG_DIR, ".recent_configs.json")
DEFAULT_CONFIG = os.path.join(CONFIG_DIR, "default_config.json")


class ConfigManager:
    """
    Singleton configuration manager.

    Handles loading/saving configuration parameters and maintains
    a list of recently used configurations.
    """
    _instance = None

    # Default parameters
    DEFAULT_PARAMS = {
        "Name": "",
        "System": "Cart",
        "Exc Wavelength": "785",
        "Detector": "256br",
        "Probe": "Microscope",
        "Spectrograph Name": "",
        "CCD X": 0.0,
        "CCD Y": 0.0,
        "Raman Shift Range": "Fingerprint",
        "Last Modified": "",
        "Config File": ""
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.params = cls.DEFAULT_PARAMS.copy()
            cls._instance.recent_configs = []
            cls._instance._ensure_config_dir()
            cls._instance._load_recent_list()
            cls._instance.load_default_config()
        return cls._instance

    def _ensure_config_dir(self):
        """Ensure config directory exists."""
        if not os.path.exists(CONFIG_DIR):
            try:
                os.makedirs(CONFIG_DIR)
            except Exception as e:
                print(f"Failed to create config directory: {e}")

    def _load_recent_list(self):
        """Load list of recently used configs."""
        if os.path.exists(RECENT_FILE):
            try:
                with open(RECENT_FILE, 'r', encoding='utf-8') as f:
                    self.recent_configs = json.load(f)
                # Filter out non-existent files
                self.recent_configs = [
                    c for c in self.recent_configs
                    if os.path.exists(c.get("path", ""))
                ]
            except Exception:
                self.recent_configs = []

    def _save_recent_list(self):
        """Save list of recently used configs."""
        try:
            with open(RECENT_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.recent_configs[:10], f, indent=2)  # Keep max 10
        except Exception as e:
            print(f"Failed to save recent list: {e}")

    def add_to_recent(self, file_path: str, name: str = ""):
        """Add a config file to recent list."""
        # Remove if already exists
        self.recent_configs = [
            c for c in self.recent_configs
            if c.get("path") != file_path
        ]
        # Add to front
        self.recent_configs.insert(0, {
            "path": file_path,
            "name": name or os.path.basename(file_path),
            "timestamp": datetime.now().isoformat()
        })
        self._save_recent_list()

    def load_default_config(self):
        """Load the default config if it exists."""
        if os.path.exists(DEFAULT_CONFIG):
            self.load_config(DEFAULT_CONFIG)

    def load_config(self, file_path: str) -> bool:
        """Load config from specified file."""
        if not os.path.exists(file_path):
            return False
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                self.params.update(loaded)
                self.params["Config File"] = file_path
                self.add_to_recent(file_path, self.params.get("Name", ""))
            return True
        except Exception as e:
            print(f"Failed to load config: {e}")
            return False

    def save_config(self, file_path: str) -> bool:
        """Save config to specified file."""
        try:
            self.params["Last Modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.params["Config File"] = file_path
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.params, f, ensure_ascii=False, indent=4)
            self.add_to_recent(file_path, self.params.get("Name", ""))
            return True
        except Exception as e:
            print(f"Failed to save config: {e}")
            return False

    def save_as_default(self) -> bool:
        """Save current config as default."""
        return self.save_config(DEFAULT_CONFIG)

    def get_summary(self) -> str:
        """Get a summary string of current configuration."""
        parts = []
        if self.params.get("Name"):
            parts.append(f"Config: {self.params['Name']}")
        parts.append(f"System: {self.params.get('System', 'N/A')}")
        parts.append(f"λ: {self.params.get('Exc Wavelength', 'N/A')} nm")
        if self.params.get("Detector"):
            parts.append(f"Detector: {self.params['Detector']}")
        parts.append(f"Range: {self.params.get('Raman Shift Range', 'N/A')}")
        return " | ".join(parts)

    def get_display_dict(self) -> dict:
        """Get dictionary of params suitable for display."""
        return {
            "Configuration Name": self.params.get("Name", "Unnamed"),
            "System Type": self.params.get("System", "N/A"),
            "Excitation Wavelength": f"{self.params.get('Exc Wavelength', 'N/A')} nm",
            "Detector": self.params.get("Detector", "N/A") or "N/A",
            "Probe Type": self.params.get("Probe", "N/A"),
            "Spectrograph": self.params.get("Spectrograph Name", "N/A") or "N/A",
            "Raman Shift Range": self.params.get("Raman Shift Range", "N/A"),
        }


class ConfigManagerUI(QDialog):
    """
    Configuration Manager Dialog with improved UX.

    Features:
    - Grouped parameters by category
    - Recent configurations sidebar
    - Quick save/load buttons
    - Clear status feedback
    """

    config_updated = pyqtSignal()

    # System options with wavelength/detector mappings
    SYSTEM_OPTIONS = {
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
            "detectors": {}
        },
        "Portable": {
            "wavelengths": ["750", "730"],
            "detectors": {}
        },
        "MANTIS": {
            "wavelengths": ["830"],
            "detectors": {"830": ["400br", "Blaze"]}
        }
    }

    PROBE_OPTIONS = ["Microscope", "Handheld", "Lensed", "SORS", "Classic"]
    RANGE_OPTIONS = ["Fingerprint", "High WVN", "Full Range", "Custom"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.inputs = {}
        self.labels = {}

        self.setWindowTitle("Configuration Manager")
        self.setMinimumSize(550, 400)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(950, int(screen.width() * 0.9)), min(680, int(screen.height() * 0.9)))
        self.move(screen.center() - self.rect().center())

        self._apply_style()
        self._build_ui()
        self._load_params_to_ui()

    def _apply_style(self):
        """Apply modern styling to the dialog."""
        self.setStyleSheet("""
            QDialog {
                background: #121212;
            }
            QGroupBox {
                font-weight: 600;
                font-size: 13px;
                border: 2px solid #333;
                border-radius: 10px;
                margin-top: 16px;
                padding: 16px 12px 12px 12px;
                background: #1a1a1a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 10px;
                color: #4C8BF5;
            }
            QLabel {
                color: #EAEAEA;
                font-size: 13px;
            }
            QLineEdit {
                padding: 10px 12px;
                border: 2px solid #333;
                border-radius: 8px;
                background: #1F1F1F;
                color: #EAEAEA;
                font-size: 13px;
                selection-background-color: #4C8BF5;
            }
            QLineEdit:focus {
                border-color: #4C8BF5;
                background: #252525;
            }
            QLineEdit::placeholder {
                color: #666;
            }
            QComboBox {
                padding: 10px 12px;
                border: 2px solid #333;
                border-radius: 8px;
                background: #1F1F1F;
                color: #EAEAEA;
                font-size: 13px;
                min-height: 20px;
            }
            QComboBox:focus {
                border-color: #4C8BF5;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #888;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #1F1F1F;
                border: 1px solid #333;
                border-radius: 6px;
                selection-background-color: #4C8BF5;
                color: #EAEAEA;
                padding: 4px;
            }
            QPushButton {
                padding: 12px 20px;
                border-radius: 8px;
                border: 2px solid #333;
                background: #1F1F1F;
                color: #EAEAEA;
                font-size: 13px;
                font-weight: 500;
                min-height: 20px;
            }
            QPushButton:hover {
                background: #2A2A2A;
                border-color: #444;
            }
            QPushButton:pressed {
                background: #333;
            }
            QPushButton:disabled {
                background: #1A1A1A;
                color: #555;
                border-color: #2A2A2A;
            }
            QPushButton[class="primary"] {
                background: #4C8BF5;
                color: white;
                border: none;
                font-weight: 600;
            }
            QPushButton[class="primary"]:hover {
                background: #5B97F7;
            }
            QPushButton[class="primary"]:pressed {
                background: #3B78E5;
            }
            QPushButton[class="success"] {
                background: #28a745;
                color: white;
                border: none;
                font-weight: 600;
            }
            QPushButton[class="success"]:hover {
                background: #218838;
            }
            QListWidget {
                background: #121212;
                border: 2px solid #333;
                border-radius: 8px;
                padding: 6px;
                outline: none;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 6px;
                margin: 3px 0;
                color: #EAEAEA;
            }
            QListWidget::item:hover {
                background: #2A2A2A;
            }
            QListWidget::item:selected {
                background: #3A5A8A;
                color: white;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #1A1A1A;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #444;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #555;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

    def _build_ui(self):
        """Build the main UI layout."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Left panel - Recent configs
        left_panel = self._build_recent_panel()
        main_layout.addWidget(left_panel, 1)

        # Right panel - Config editor
        right_panel = self._build_editor_panel()
        main_layout.addWidget(right_panel, 3)

    def _build_recent_panel(self) -> QWidget:
        """Build the recent configurations panel."""
        panel = QFrame()
        panel.setObjectName("recentPanel")
        panel.setStyleSheet("""
            QFrame#recentPanel {
                background: #1A1A1A;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Title
        title = QLabel("Recent Configurations")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet("color: #AAAAAA;")
        layout.addWidget(title)

        # Recent list
        self.recent_list = QListWidget()
        self.recent_list.setStyleSheet("""
            QListWidget {
                background: #121212;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px 0;
            }
            QListWidget::item:hover {
                background: #2A2A2A;
            }
            QListWidget::item:selected {
                background: #3A5A8A;
            }
        """)
        self.recent_list.itemDoubleClicked.connect(self._load_recent_item)
        self._populate_recent_list()
        layout.addWidget(self.recent_list)

        # Load selected button
        btn_load_selected = QPushButton("Load Selected")
        btn_load_selected.clicked.connect(self._load_selected_recent)
        layout.addWidget(btn_load_selected)

        # New config button
        btn_new = QPushButton("New Configuration")
        btn_new.setProperty("class", "success")
        btn_new.clicked.connect(self._new_config)
        layout.addWidget(btn_new)

        return panel

    def _build_editor_panel(self) -> QWidget:
        """Build the configuration editor panel."""
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Scroll area for form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(12)

        # Basic Info Group
        basic_group = QGroupBox("Basic Information")
        basic_layout = QGridLayout(basic_group)
        basic_layout.setSpacing(8)

        # Name
        basic_layout.addWidget(QLabel("Configuration Name:"), 0, 0)
        self.inputs["Name"] = QLineEdit()
        self.inputs["Name"].setPlaceholderText("Enter a name for this configuration")
        basic_layout.addWidget(self.inputs["Name"], 0, 1)

        # Spectrograph Name
        basic_layout.addWidget(QLabel("Spectrograph Name:"), 1, 0)
        self.inputs["Spectrograph Name"] = QLineEdit()
        self.inputs["Spectrograph Name"].setPlaceholderText("Optional spectrograph identifier")
        basic_layout.addWidget(self.inputs["Spectrograph Name"], 1, 1)

        form_layout.addWidget(basic_group)

        # System Settings Group
        system_group = QGroupBox("System Settings")
        system_layout = QGridLayout(system_group)
        system_layout.setSpacing(8)

        # System
        system_layout.addWidget(QLabel("System Type:"), 0, 0)
        self.inputs["System"] = QComboBox()
        self.inputs["System"].addItems(list(self.SYSTEM_OPTIONS.keys()))
        self.inputs["System"].currentIndexChanged.connect(self._on_system_changed)
        system_layout.addWidget(self.inputs["System"], 0, 1)

        # Wavelength
        system_layout.addWidget(QLabel("Excitation Wavelength:"), 1, 0)
        self.inputs["Exc Wavelength"] = QComboBox()
        self.inputs["Exc Wavelength"].currentIndexChanged.connect(self._on_wavelength_changed)
        system_layout.addWidget(self.inputs["Exc Wavelength"], 1, 1)

        # Detector
        self.labels["Detector"] = QLabel("Detector:")
        system_layout.addWidget(self.labels["Detector"], 2, 0)
        self.inputs["Detector"] = QComboBox()
        system_layout.addWidget(self.inputs["Detector"], 2, 1)

        # Probe
        system_layout.addWidget(QLabel("Probe Type:"), 3, 0)
        self.inputs["Probe"] = QComboBox()
        self.inputs["Probe"].addItems(self.PROBE_OPTIONS)
        system_layout.addWidget(self.inputs["Probe"], 3, 1)

        form_layout.addWidget(system_group)

        # Measurement Settings Group
        measure_group = QGroupBox("Measurement Settings")
        measure_layout = QGridLayout(measure_group)
        measure_layout.setSpacing(8)

        # Raman Shift Range
        measure_layout.addWidget(QLabel("Raman Shift Range:"), 0, 0)
        self.inputs["Raman Shift Range"] = QComboBox()
        self.inputs["Raman Shift Range"].addItems(self.RANGE_OPTIONS)
        measure_layout.addWidget(self.inputs["Raman Shift Range"], 0, 1)

        # CCD X
        measure_layout.addWidget(QLabel("CCD X Position:"), 1, 0)
        self.inputs["CCD X"] = QLineEdit()
        self.inputs["CCD X"].setPlaceholderText("0.0")
        measure_layout.addWidget(self.inputs["CCD X"], 1, 1)

        # CCD Y
        measure_layout.addWidget(QLabel("CCD Y Position:"), 2, 0)
        self.inputs["CCD Y"] = QLineEdit()
        self.inputs["CCD Y"].setPlaceholderText("0.0")
        measure_layout.addWidget(self.inputs["CCD Y"], 2, 1)

        form_layout.addWidget(measure_group)

        # Status info
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet("""
            QFrame {
                background: #1A1A1A;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        status_layout = QHBoxLayout(self.status_frame)
        self.lbl_status = QLabel("No configuration loaded")
        self.lbl_status.setStyleSheet("color: #888;")
        status_layout.addWidget(self.lbl_status)
        form_layout.addWidget(self.status_frame)

        form_layout.addStretch()
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)

        # Button bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_load = QPushButton("Load from File...")
        btn_load.clicked.connect(self._load_from_file)
        btn_layout.addWidget(btn_load)

        btn_layout.addStretch()

        btn_save_default = QPushButton("Save as Default")
        btn_save_default.clicked.connect(self._save_as_default)
        btn_layout.addWidget(btn_save_default)

        btn_save_as = QPushButton("Save As...")
        btn_save_as.clicked.connect(self._save_as_file)
        btn_layout.addWidget(btn_save_as)

        btn_save = QPushButton("Save && Continue")
        btn_save.setProperty("class", "primary")
        btn_save.clicked.connect(self._save_and_continue)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        return panel

    def _populate_recent_list(self):
        """Populate the recent configurations list."""
        self.recent_list.clear()
        for config in self.config.recent_configs:
            item = QListWidgetItem(config.get("name", "Unnamed"))
            item.setToolTip(config.get("path", ""))
            item.setData(Qt.UserRole, config.get("path"))
            self.recent_list.addItem(item)

    def _load_params_to_ui(self):
        """Load current config params to UI widgets."""
        params = self.config.params

        # Text fields
        for key in ["Name", "Spectrograph Name"]:
            if key in self.inputs:
                self.inputs[key].setText(str(params.get(key, "")))

        # CCD fields
        self.inputs["CCD X"].setText(str(params.get("CCD X", 0.0)))
        self.inputs["CCD Y"].setText(str(params.get("CCD Y", 0.0)))

        # System combo
        system = params.get("System", "Cart")
        idx = self.inputs["System"].findText(system)
        if idx >= 0:
            self.inputs["System"].setCurrentIndex(idx)
        self._on_system_changed()

        # Set wavelength after system update
        wl = params.get("Exc Wavelength", "")
        wl_idx = self.inputs["Exc Wavelength"].findText(wl)
        if wl_idx >= 0:
            self.inputs["Exc Wavelength"].setCurrentIndex(wl_idx)
        self._on_wavelength_changed()

        # Set detector after wavelength update
        det = params.get("Detector", "")
        if det and self.inputs["Detector"].isVisible():
            det_idx = self.inputs["Detector"].findText(det)
            if det_idx >= 0:
                self.inputs["Detector"].setCurrentIndex(det_idx)

        # Probe
        probe = params.get("Probe", "Microscope")
        probe_idx = self.inputs["Probe"].findText(probe)
        if probe_idx >= 0:
            self.inputs["Probe"].setCurrentIndex(probe_idx)

        # Range
        range_val = params.get("Raman Shift Range", "Fingerprint")
        range_idx = self.inputs["Raman Shift Range"].findText(range_val)
        if range_idx >= 0:
            self.inputs["Raman Shift Range"].setCurrentIndex(range_idx)

        # Update status
        self._update_status()

    def _collect_ui_to_params(self) -> bool:
        """Collect UI values to config params. Returns False if validation fails."""
        params = self.config.params

        # Text fields
        params["Name"] = self.inputs["Name"].text().strip()
        params["Spectrograph Name"] = self.inputs["Spectrograph Name"].text().strip()

        # Combos
        params["System"] = self.inputs["System"].currentText()
        params["Exc Wavelength"] = self.inputs["Exc Wavelength"].currentText()
        params["Detector"] = self.inputs["Detector"].currentText() if self.inputs["Detector"].isVisible() else ""
        params["Probe"] = self.inputs["Probe"].currentText()
        params["Raman Shift Range"] = self.inputs["Raman Shift Range"].currentText()

        # CCD values
        try:
            params["CCD X"] = float(self.inputs["CCD X"].text() or 0)
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "CCD X must be a number.")
            return False

        try:
            params["CCD Y"] = float(self.inputs["CCD Y"].text() or 0)
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "CCD Y must be a number.")
            return False

        return True

    def _on_system_changed(self):
        """Handle system type change."""
        system = self.inputs["System"].currentText()
        options = self.SYSTEM_OPTIONS.get(system, {})
        wavelengths = options.get("wavelengths", [])

        # Update wavelength options
        self.inputs["Exc Wavelength"].clear()
        self.inputs["Exc Wavelength"].addItems(wavelengths)

        self._on_wavelength_changed()

    def _on_wavelength_changed(self):
        """Handle wavelength change."""
        system = self.inputs["System"].currentText()
        wavelength = self.inputs["Exc Wavelength"].currentText()
        options = self.SYSTEM_OPTIONS.get(system, {})
        detectors = options.get("detectors", {}).get(wavelength, [])

        # Update detector options
        self.inputs["Detector"].clear()
        if detectors:
            self.inputs["Detector"].addItems(detectors)
            self.inputs["Detector"].setVisible(True)
            self.labels["Detector"].setVisible(True)
        else:
            self.inputs["Detector"].setVisible(False)
            self.labels["Detector"].setVisible(False)

    def _update_status(self):
        """Update status label."""
        config_file = self.config.params.get("Config File", "")
        if config_file:
            self.lbl_status.setText(f"Loaded: {os.path.basename(config_file)}")
        else:
            self.lbl_status.setText("New configuration (not saved)")

    def _load_recent_item(self, item: QListWidgetItem):
        """Load a recent config item on double-click."""
        path = item.data(Qt.UserRole)
        if path and os.path.exists(path):
            if self.config.load_config(path):
                self._load_params_to_ui()
                QMessageBox.information(self, "Loaded", f"Configuration loaded:\n{os.path.basename(path)}")

    def _load_selected_recent(self):
        """Load the selected recent config."""
        item = self.recent_list.currentItem()
        if item:
            self._load_recent_item(item)
        else:
            QMessageBox.warning(self, "No Selection", "Please select a configuration to load.")

    def _new_config(self):
        """Create a new blank configuration."""
        self.config.params = ConfigManager.DEFAULT_PARAMS.copy()
        self._load_params_to_ui()
        self.lbl_status.setText("New configuration (not saved)")

    def _load_from_file(self):
        """Load configuration from file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration",
            CONFIG_DIR,
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            if self.config.load_config(file_path):
                self._load_params_to_ui()
                self._populate_recent_list()
                QMessageBox.information(self, "Loaded", f"Configuration loaded:\n{os.path.basename(file_path)}")
            else:
                QMessageBox.critical(self, "Error", "Failed to load configuration file.")

    def _save_as_default(self):
        """Save current config as default."""
        if not self._collect_ui_to_params():
            return
        if self.config.save_as_default():
            self._update_status()
            QMessageBox.information(self, "Saved", "Configuration saved as default.\nThis will be loaded automatically on startup.")
        else:
            QMessageBox.critical(self, "Error", "Failed to save default configuration.")

    def _save_as_file(self):
        """Save configuration to a new file."""
        if not self._collect_ui_to_params():
            return

        name = self.config.params.get("Name", "").strip()
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        default_name = f"{safe_name}.json" if safe_name else "config.json"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration",
            os.path.join(CONFIG_DIR, default_name),
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            if self.config.save_config(file_path):
                self._update_status()
                self._populate_recent_list()
                QMessageBox.information(self, "Saved", f"Configuration saved:\n{file_path}")
            else:
                QMessageBox.critical(self, "Error", "Failed to save configuration.")

    def _save_and_continue(self):
        """Save config and close dialog."""
        if not self._collect_ui_to_params():
            return

        # If no file path, save as default
        config_file = self.config.params.get("Config File", "")
        if config_file:
            success = self.config.save_config(config_file)
        else:
            success = self.config.save_as_default()

        if success:
            self.config_updated.emit()
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to save configuration.")


# Quick test
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    # Apply dark theme for testing
    app.setStyleSheet("""
        QWidget {
            font-family: 'Segoe UI';
            color: #EAEAEA;
            background: #121212;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #333;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }
        QPushButton {
            background: #1F1F1F;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
        }
        QPushButton:hover { background: #2A2A2A; }
        QLineEdit, QComboBox {
            background: #1F1F1F;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 6px;
        }
    """)

    dlg = ConfigManagerUI()
    if dlg.exec_():
        print("Config saved")
        print("Summary:", dlg.config.get_summary())
    sys.exit(app.exec_())
