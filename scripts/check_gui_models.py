"""Exercise real GUI preparation offscreen and measure event-loop responsiveness."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import json
from pathlib import Path
from time import monotonic
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from speech_translator.config import load_config
from speech_translator.gui.main_window import MainWindow, configure_font

app = QApplication([])
configure_font(app)
window = MainWindow(load_config(Path('config.yaml')), Path('artifacts/gui-devices.json'),
                    {'mic_a': 25, 'mic_b': 26, 'speaker_a': 23, 'speaker_b': 20})
window.show()
started = monotonic()
ticks = []
preparing = False
result = 1

def tick():
    global preparing, result
    ticks.append(monotonic())
    if not preparing and not window.loading:
        preparing = True
        window.initialize()
    elif preparing and not window.loading:
        result = 0 if window.ready else 1
        window.grab().save('artifacts/gui-ready.png')
        report = {'ready': window.ready, 'elapsed_sec': monotonic() - started,
                  'event_loop_ticks': len(ticks),
                  'max_tick_gap_sec': max((b - a for a, b in zip(ticks, ticks[1:])), default=0),
                  'status': window.status.toPlainText()}
        Path('artifacts/gui-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False), flush=True)
        timer.stop()
        window.close()
    elif monotonic() - started > 180:
        timer.stop()
        window.close()

timer = QTimer()
timer.timeout.connect(tick)
timer.start(100)
app.exec()
raise SystemExit(result)
