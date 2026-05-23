import sys
from ui.MainWindow_ui import Ui_MainWindow
from PySide6.QtWidgets import QApplication, QMainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)


def main() -> None:
    app = QApplication(sys.argv)
    # TODO: instantiate and show the main window
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
