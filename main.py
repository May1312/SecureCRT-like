import sys
import traceback
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow

def exception_hook(exctype, value, tb):
    """全局异常处理"""
    traceback.print_exception(exctype, value, tb)
    sys.__excepthook__(exctype, value, tb)
    sys.exit(1)

if __name__ == "__main__":
    sys.excepthook = exception_hook
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 