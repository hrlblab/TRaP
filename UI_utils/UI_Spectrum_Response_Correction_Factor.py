import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel,
    QPushButton, QHBoxLayout, QMessageBox, QFileDialog
)
from scipy.io import loadmat

# ⬇ 修改为你的真实路径
from UI_utils.UI_Calibration import WaveformSelectionUI


class SpectrumCorrectionProcessUI(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spectrum Correction Process UI")
        self.setFixedSize(520, 300)
        self.result = None
        self.wvn = None
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.set_question(
            "Do you have a spectral response calibration factor?",
            yes_handler=self.on_have_factor,
            no_handler=self.on_no_factor
        )

    def set_question(self, text, yes_handler=None, no_handler=None):
        self.clear_layout()
        label = QLabel(text)
        self.layout.addWidget(label)

        btn_layout = QHBoxLayout()
        btn_yes = QPushButton("Yes")
        btn_no = QPushButton("No")
        if yes_handler:
            btn_yes.clicked.connect(yes_handler)
        if no_handler:
            btn_no.clicked.connect(no_handler)
        btn_layout.addWidget(btn_yes)
        btn_layout.addWidget(btn_no)
        self.layout.addLayout(btn_layout)

    def clear_layout(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def on_have_factor(self):
        self.result = "HaveFactor"
        self.accept()

    def on_no_factor(self):
        reply = QMessageBox.question(
            self,
            "X Axis Calibration",
            "Do you have an X Axis Calibration File (.mat)?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select X Axis Calibration File",
                "",
                "MAT files (*.mat);;All Files (*)"
            )
            if not file_path:
                QMessageBox.warning(self, "No File", "No file selected.")
                return
            try:
                mat = loadmat(file_path)
                if "Cal" in mat and isinstance(mat["Cal"], np.ndarray):
                    cal_struct = mat["Cal"]
                    if "Wvn" in cal_struct.dtype.names:
                        self.wvn = cal_struct["Wvn"][0, 0].flatten()
                        self.result = "WvnUploaded"
                        self.accept()
                        return
                QMessageBox.warning(self, "Invalid File", "Missing Cal['Wvn']")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
        else:
            # self.calib_ui = WaveformSelectionUI()
            # self.calib_ui.show()

            QMessageBox.information(
                self,
                "Complete Calibration",
                "Please complete the X Axis Calibration in the opened window,\nthen save it as a .mat file.\n\nClick OK to continue when done."
            )

            # file_path, _ = QFileDialog.getOpenFileName(
            #     self,
            #     "Select Saved Calibration File (.mat)",
            #     "",
            #     "MAT files (*.mat);;All Files (*)"
            # )
            # if not file_path:
            #     QMessageBox.warning(self, "Error", "No calibration file selected.")
            #     return
            # try:
            #     mat = loadmat(file_path)
            #     if "Cal" in mat and isinstance(mat["Cal"], np.ndarray):
            #         cal_struct = mat["Cal"]
            #         if "Wvn" in cal_struct.dtype.names:
            #             self.wvn = cal_struct["Wvn"][0, 0].flatten()
            #             self.result = "WvnUploaded"
            #             self.accept()
            #             return
            #     QMessageBox.warning(self, "Invalid File", "Missing Cal['Wvn']")
            # except Exception as e:
            #     QMessageBox.critical(self, "Error", str(e))

        self.set_question(
            "Choose source for correction:\nWhite Light or Standard?",
            yes_handler=lambda: self.on_choose_source("WhiteLight"),
            no_handler=lambda: self.on_choose_source("Standard")
        )


    def on_choose_source(self, source):
        if source == "Standard":
            self.result = "Standard_NIST"
            self.accept()
        else:
            self.set_question(
                "Use orient coefficient?",
                yes_handler=self.on_orient_coeff,
                no_handler=self.on_no_orient
            )

    def on_orient_coeff(self):
        self.result = "OrientCoeff"
        self.accept()

    def on_no_orient(self):
        self.set_question(
            "Enter coefficients for WL spectrum?",
            yes_handler=self.on_enter_coeff,
            no_handler=self.on_no_coeff
        )

    def on_enter_coeff(self):
        self.result = "EnterCoeff"
        self.accept()

    def on_no_coeff(self):
        self.result = "NoCoeff"
        self.accept()


# ✅ Optional Test
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = SpectrumCorrectionProcessUI()
    if dlg.exec_():
        print("Result:", dlg.result)
        if dlg.result == "WvnUploaded":
            print("Wvn Length:", len(dlg.wvn))
    else:
        print("Cancelled")
