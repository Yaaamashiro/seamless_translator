"""Render the real GUI without loading models or starting recording."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from speech_translator.config import load_config
from speech_translator.gui.main_window import MainWindow, configure_font

app = QApplication([])
configure_font(app)
window = MainWindow(load_config(Path('config.yaml')), Path('config.local.json'))
window.show()

def capture():
    if window.loading:
        QTimer.singleShot(100, capture)
        return
    Path('artifacts').mkdir(exist_ok=True)
    window.grab().save('artifacts/gui.png')
    window.close()
    app.quit()

QTimer.singleShot(200, capture)
app.exec()
