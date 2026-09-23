import sys
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QFont, QFontDatabase
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                              QLabel, QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget)

from speech_translator.audio.devices import list_devices
from speech_translator.audio.selection import ROLES, load_selection, resolve_saved, save_selection
from speech_translator.logging.session_logger import SessionLogger
from speech_translator.pipeline.coordinator import Coordinator, build_channels
from speech_translator.pipeline.engines import load_engines, close_engines


class Bridge(QObject):
    event = Signal(object)
    devices = Signal(object)
    prepared = Signal(object)
    status = Signal(str)
    failure = Signal(str)
    automatic = Signal(bool, str)


class MainWindow(QMainWindow):
    def __init__(self, config, selection_path, explicit=None):
        super().__init__()
        self.config, self.selection_path = config, Path(selection_path)
        self.explicit = explicit or {}
        self.engines = None
        self.coordinator = None
        self.automatic = None
        self.loading = False
        self.closing = False
        self.ready = False
        self.futures = []
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='startup')
        self.bridge = Bridge()
        self.bridge.event.connect(self.on_event)
        self.bridge.devices.connect(self.on_devices)
        self.bridge.prepared.connect(self.on_prepared)
        self.bridge.status.connect(self.show_status)
        self.bridge.failure.connect(self.on_failure)
        self.bridge.automatic.connect(self.on_automatic_status)
        self.setWindowTitle('Two-Way Speech Translator')
        self.resize(960, 860)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        title = QLabel('対面音声翻訳  /  日本語 ⇄ English')
        title.setStyleSheet('font-size: 23px; font-weight: 600; padding: 8px 0;')
        layout.addWidget(title)
        layout.addWidget(QLabel('① 機器を選択 → ② 準備 → ③ 自動翻訳を開始  /  手動録音: キー1・2'))
        device_group = QGroupBox('オーディオ機器')
        form = QFormLayout(device_group)
        self.selectors = {}
        for role, label in [('mic_a', 'Microphone A（日本語）'), ('speaker_a', 'Speaker A（日本語を出力）'),
                            ('mic_b', 'Microphone B（English）'), ('speaker_b', 'Speaker B（英語を出力）')]:
            combo = QComboBox()
            combo.setMinimumWidth(400)
            combo.currentIndexChanged.connect(self.invalidate)
            self.selectors[role] = combo
            form.addRow(label, combo)
        actions = QHBoxLayout()
        self.refresh = QPushButton('デバイスを再取得')
        self.refresh.clicked.connect(self.scan)
        self.prepare = QPushButton('設定を保存して準備')
        self.prepare.clicked.connect(self.initialize)
        actions.addWidget(self.refresh)
        actions.addWidget(self.prepare)
        form.addRow(actions)
        layout.addWidget(device_group)
        self.auto_button = QPushButton('自動翻訳を開始（ターン制）')
        self.auto_button.setMinimumHeight(40)
        self.auto_button.clicked.connect(self.toggle_automatic)
        layout.addWidget(self.auto_button)
        self.auto_status = QLabel('自動モード停止中：マイクA＝日本語、マイクB＝英語。準備後に開始できます。')
        self.auto_status.setWordWrap(True)
        layout.addWidget(self.auto_status)
        self.route = QLabel('Mic A → Speaker B  /  Mic B → Speaker A')
        self.route.setWordWrap(True)
        layout.addWidget(self.route)
        panels = QHBoxLayout()
        self.panels = {}
        self.states = {'A_TO_B': 'IDLE', 'B_TO_A': 'IDLE'}
        for direction, title, side in [('A_TO_B', 'A → B  /  日本語 → English', 'A'),
                                        ('B_TO_A', 'B → A  /  English → 日本語', 'B')]:
            box = QGroupBox(title)
            column = QVBoxLayout(box)
            button = QPushButton(f'Start {side} Recording')
            button.setMinimumHeight(44)
            button.clicked.connect(lambda checked=False, d=direction: self.toggle(d))
            column.addWidget(button)
            column.addWidget(QLabel('ASR / 認識結果'))
            source = QTextEdit()
            source.setReadOnly(True)
            column.addWidget(source)
            column.addWidget(QLabel('Translation / 翻訳結果'))
            target = QTextEdit()
            target.setReadOnly(True)
            column.addWidget(target)
            state = QLabel('IDLE')
            latency = QLabel('Total latency: —')
            error = QLabel('')
            error.setWordWrap(True)
            error.setStyleSheet('color: #b42318;')
            column.addWidget(state)
            column.addWidget(latency)
            column.addWidget(error)
            self.panels[direction] = dict(button=button, source=source, target=target,
                                          state=state, latency=latency, error=error)
            panels.addWidget(box)
        layout.addLayout(panels, 1)
        self.status = QTextEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(125)
        layout.addWidget(self.status)
        # Specify foregrounds together with backgrounds: Windows dark-mode
        # text must never be inherited onto our fixed light surfaces.
        self.setStyleSheet("""
            QWidget { color: #172b4d; background-color: #f4f6fa; }
            QGroupBox {
                font-weight: 600; border: 1px solid #b8c4d4;
                border-radius: 6px; margin-top: 12px; padding-top: 10px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QTextEdit, QComboBox {
                color: #172b4d; background-color: #ffffff;
                border: 1px solid #94a3b8; border-radius: 4px; padding: 4px;
                selection-color: #ffffff; selection-background-color: #1d4ed8;
            }
            QComboBox QAbstractItemView {
                color: #172b4d; background-color: #ffffff;
                selection-color: #ffffff; selection-background-color: #1d4ed8;
            }
            QPushButton {
                color: #172b4d; background-color: #ffffff;
                border: 1px solid #94a3b8; border-radius: 4px; padding: 7px;
            }
            QPushButton:hover { background-color: #e0eaff; border-color: #1d4ed8; }
            QPushButton:pressed { background-color: #c7d8ff; }
            QPushButton:focus, QComboBox:focus, QTextEdit:focus { border: 2px solid #1d4ed8; }
            QPushButton:disabled, QComboBox:disabled {
                color: #526174; background-color: #e2e8f0; border-color: #b8c4d4;
            }
            QToolTip { color: #172b4d; background-color: #ffffff; border: 1px solid #94a3b8; }
        """)
        self.shortcuts = []
        for key, direction in [('1', 'A_TO_B'), ('2', 'B_TO_A')]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(lambda d=direction: self.toggle(d))
            self.shortcuts.append(shortcut)
        self.show_status(f'✓ Python {sys.version.split()[0]}')
        self.scan()

    def submit(self, task):
        self.futures.append(self.executor.submit(task))

    @Slot(str)
    def show_status(self, message):
        self.status.append(message)

    @Slot()
    def invalidate(self):
        self.ready = False
        self.update_controls()

    def scan(self):
        self.loading = True
        self.ready = False
        self.update_controls()

        def work():
            try:
                self.bridge.devices.emit(list_devices())
            except Exception as exc:
                self.bridge.failure.emit(str(exc))
        self.submit(work)

    @Slot(object)
    def on_devices(self, devices):
        self.loading = False
        try:
            saved = load_selection(self.selection_path)
        except Exception as exc:
            saved = {}
            self.show_status(f'保存設定を読み込めません: {exc}')
        for role, combo in self.selectors.items():
            previous = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem('選択してください', None)
            candidates = sorted([d for d in devices if getattr(d, ROLES[role]) > 0],
                                key=lambda d: (d.host_api != 'Windows WASAPI', d.index))
            restored = resolve_saved(previous.to_dict() if previous else saved.get(role), candidates)
            for device in candidates:
                combo.addItem(f'{device.index}: {device.name} [{device.host_api}]', device)
                explicit = self.explicit.get(role)
                if (explicit is not None and explicit == device.index) or (explicit is None and device == restored):
                    combo.setCurrentIndex(combo.count() - 1)
            combo.blockSignals(False)
        self.explicit = {}
        self.show_status('機器を4つ選んで「設定を保存して準備」を押してください。初回はモデル取得が必要です。')
        self.update_controls()

    def initialize(self):
        selected = {role: combo.currentData() for role, combo in self.selectors.items()}
        if any(device is None for device in selected.values()):
            self.show_status('Mic A / Mic B / Speaker A / Speaker Bをすべて選んでください。')
            return
        if selected['mic_a'].index == selected['mic_b'].index or selected['speaker_a'].index == selected['speaker_b'].index:
            self.show_status('AとBには別の機器を指定してください。同一機器の別API選択にも注意してください。')
            return
        self.loading = True
        self.ready = False
        self.update_controls()

        def work():
            engines = None
            try:
                import sounddevice as sd
                for role, device in selected.items():
                    rate = device.default_sample_rate
                    if role.startswith('mic'):
                        sd.check_input_settings(device=device.index, channels=device.input_channels,
                                                samplerate=rate, dtype='float32')
                    else:
                        sd.check_output_settings(device=device.index, channels=min(2, device.output_channels),
                                                 samplerate=rate, dtype='float32')
                    self.bridge.status.emit(f'✓ {role}: {device.name}')
                engines = self.engines or load_engines(self.config, self.bridge.status.emit)
                if self.closing:
                    close_engines(engines)
                    return
                save_selection(self.selection_path, selected)
                self.bridge.prepared.emit((selected, engines))
            except Exception as exc:
                if engines is not None and engines is not self.engines:
                    close_engines(engines)
                self.bridge.failure.emit(f'準備失敗: {type(exc).__name__}: {exc}')
        self.submit(work)

    @Slot(object)
    def on_prepared(self, result):
        selected, self.engines = result
        self.loading = False
        if self.closing:
            close_engines(self.engines)
            self.engines = None
            return
        if self.coordinator:
            self.futures.extend(self.coordinator.close())
        logger = SessionLogger(self.config['application']['log_directory'], self.config['application']['save_logs'])
        self.coordinator = Coordinator(build_channels(selected, self.engines, self.config, logger,
                                                       self.bridge.event.emit))
        self.states = {'A_TO_B': 'IDLE', 'B_TO_A': 'IDLE'}
        self.route.setText(f'A: {selected["mic_a"].name} → B: {selected["speaker_b"].name}\n'
                           f'B: {selected["mic_b"].name} → A: {selected["speaker_a"].name}')
        self.ready = True
        for direction in self.states:
            self.on_event({'direction': direction, 'state': 'IDLE', 'error': ''})
        self.show_status('✓ 準備完了。「自動翻訳を開始」を押して一人ずつ話してください。手動録音も利用できます。')
        self.update_controls()

    @Slot(str)
    def on_failure(self, message):
        self.loading = False
        self.ready = False
        self.show_status(message + '\n接続・設定を確認し、準備を再実行してください。')
        self.update_controls()

    def toggle(self, direction):
        if self.automatic is not None:
            return
        if self.ready and not self.closing and self.panels[direction]['button'].isEnabled():
            self.coordinator.toggle(direction)
            # Reflect state synchronously, before a second shortcut/click arrives.
            self.states = {key: c.state.name for key, c in self.coordinator.channels.items()}
            self.update_controls()

    @Slot(object)
    def on_event(self, event):
        direction = event['direction']
        panel = self.panels[direction]
        if 'state' in event:
            self.states[direction] = event['state']
            panel['state'].setText(event['state'])
        for key, widget in [('asr_text', 'source'), ('translated_text', 'target')]:
            if key in event:
                panel[widget].setPlainText(event[key])
        if 'error' in event:
            panel['error'].setText(event['error'])
        if 'total_latency_sec' in event:
            latency = event['total_latency_sec']
            panel['latency'].setText('Total latency: —' if latency is None else f'Total latency: {latency:.2f} sec')
        self.update_controls()

    @Slot()
    def toggle_automatic(self):
        if self.automatic is not None:
            self.automatic.stop()
            self.auto_status.setText('自動翻訳を停止中…')
            self.auto_button.setEnabled(False)
            return
        if not self.ready or self.closing or any(state not in ('IDLE', 'ERROR') for state in self.states.values()):
            return
        from speech_translator.pipeline.automatic import AutomaticConversation
        self.automatic = AutomaticConversation(self.coordinator.channels, self.config, self.bridge.automatic.emit)
        self.futures.append(self.automatic.start())
        self.update_controls()

    @Slot(bool, str)
    def on_automatic_status(self, running, message):
        self.auto_status.setText(message)
        if not running:
            self.automatic = None
            self.show_status(message)
        self.update_controls()

    def update_controls(self):
        busy = any(state not in ('IDLE', 'ERROR') for state in self.states.values())
        auto_running = self.automatic is not None
        editable = not (busy or self.loading or self.closing or auto_running)
        self.auto_button.setText('自動翻訳を停止' if auto_running else '自動翻訳を開始（ターン制）')
        self.auto_button.setEnabled(not self.closing and
            ((auto_running and not self.automatic.stopping.is_set()) or
             (not auto_running and self.ready and not busy and not self.loading)))
        for combo in self.selectors.values():
            combo.setEnabled(editable)
        self.refresh.setEnabled(editable)
        self.prepare.setEnabled(editable)
        for direction, panel in self.panels.items():
            state = self.states[direction]
            side = 'A' if direction == 'A_TO_B' else 'B'
            panel['button'].setText(f'{"Stop" if state == "RECORDING" else "Start"} {side} Recording')
            panel['button'].setEnabled(self.ready and not self.closing and not auto_running and
                                       (state == 'RECORDING' or (not busy and state in ('IDLE', 'ERROR'))))

    def closeEvent(self, event):
        if not self.closing:
            self.closing = True
            if self.automatic is not None:
                self.automatic.stop()
            if self.coordinator:
                self.futures.extend(self.coordinator.close())
            self.executor.shutdown(wait=False)
        if any(not f.done() for f in self.futures):
            event.ignore()
            self.show_status('終了処理中です。実行中のモデル処理が戻るまでお待ちください。')
            self.update_controls()
            QTimer.singleShot(500, self.close)
        else:
            close_engines(self.engines)
            self.engines = None
            event.accept()


def configure_font(app):
    # Also support offscreen Qt, whose system font database can be empty on Windows.
    if sys.platform == 'win32':
        path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'meiryo.ttc'
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
        app.setFont(QFont('Meiryo', 10))


def run_gui(config, selection_path, explicit=None):
    app = QApplication.instance() or QApplication(sys.argv[:1])
    configure_font(app)
    window = MainWindow(config, selection_path, explicit)
    window.show()
    return app.exec()
