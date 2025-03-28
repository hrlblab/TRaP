import sys
import time
from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

from UI_utils.UI_System_Select import MainWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)

    splash_pix = QPixmap("resources/loading.png")
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.setMask(splash_pix.mask())
    splash.show()


    for i in range(1, 4):
        splash.showMessage(f"Loading... ({i}/3)", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        app.processEvents()
        time.sleep(0.3)

    mainWin = MainWindow()
    mainWin.show()
    splash.finish(mainWin)

    sys.exit(app.exec_())