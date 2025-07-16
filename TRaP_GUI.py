import sys
import ctypes
import platform
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QSharedMemory
from UI_utils.UI_System_Select import MainWindow
from UI_utils.UI_wizard import SystemSelectWizard

# Unique application identifier
APP_ID = 'TRaP.1.0'

def main():
    # Windows taskbar fix
    if platform.system() == 'Windows':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)

    # Prevent multiple instances
    shared_mem = QSharedMemory(APP_ID)
    if not shared_mem.create(512):
        QMessageBox.warning(None, "Warning", "Application is already running!")
        sys.exit(1)

    # 创建并显示主窗口
    app = QApplication(sys.argv)
    main_win = SystemSelectWizard()
    main_win.show()

    # 当主窗口关闭时，释放共享内存
    exit_code = app.exec_()
    shared_mem.detach()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()