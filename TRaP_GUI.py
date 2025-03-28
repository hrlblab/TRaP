import sys
import time
import ctypes
import platform
from PyQt5.QtWidgets import (QApplication, QSplashScreen, QMainWindow,
                             QMessageBox, QLabel, QProgressBar)
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt, QTimer, QSharedMemory
from UI_utils.UI_System_Select import MainWindow

# Unique application identifier
APP_ID = 'com.yourcompany.yourapp.1.0'


class SplashScreen(QSplashScreen):
    def __init__(self, pixmap):
        pixmap = QPixmap(":/resources/loading.png")
        super().__init__(pixmap, Qt.WindowStaysOnTopHint)
        self.progress = 0
        self.message = "Starting application..."

    def set_progress(self, value, message=None):
        self.progress = value
        if message:
            self.message = message
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, painter):
        super().drawContents(painter)
        painter.setPen(QColor(255, 255, 255))

        # Draw progress bar
        bar_width = self.width() - 40
        painter.drawRect(20, self.height() - 40, bar_width, 20)
        painter.fillRect(20, self.height() - 40, int(bar_width * (self.progress / 100)), 20, QColor(0, 150, 255))

        # Draw text
        painter.drawText(20, self.height() - 50, self.message)
        painter.drawText(self.width() - 100, self.height() - 50, f"{self.progress}%")


def main():
    # Windows taskbar fix
    if platform.system() == 'Windows':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)

    # Prevent multiple instances
    shared_mem = QSharedMemory(APP_ID)
    if not shared_mem.create(512):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Application is already running!")
        msg.setWindowTitle("Warning")
        msg.exec_()
        sys.exit(1)

    app = QApplication(sys.argv)

    # Load splash image
    try:
        pixmap = QPixmap(":/splash.png")  # Use resource system for embedded images
    except:
        pixmap = QPixmap("resources/loading.png")

    splash = SplashScreen(pixmap)
    splash.show()

    # Immediate visual feedback
    splash.set_progress(5, "Initializing core...")

    # Create main window in background
    main_win = MainWindow()

    # Simulated loading process
    def update_progress():
        current = splash.progress
        if current < 25:
            splash.set_progress(current + 5, "Loading modules...")
        elif current < 50:
            splash.set_progress(current + 5, "Initializing components...")
        elif current < 75:
            splash.set_progress(current + 5, "Preparing UI...")
        else:
            splash.set_progress(current + 5, "Almost ready...")

        if current >= 95:
            timer.stop()
            main_win.show()
            splash.finish(main_win)
            # Release shared memory when done
            shared_mem.detach()

    # Setup loading timer
    timer = QTimer()
    timer.timeout.connect(update_progress)
    timer.start(150)  # Update every 150ms

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()