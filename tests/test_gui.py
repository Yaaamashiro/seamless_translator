import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from speech_translator.audio.devices import AudioDevice
from speech_translator.config import load_config
from speech_translator.gui.main_window import MainWindow


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        devices = [AudioDevice(i, f'Test {i}', 'Windows WASAPI', 2 if i < 2 else 0,
                               0 if i < 2 else 2, 48000) for i in range(4)]
        self.patch = patch('speech_translator.gui.main_window.list_devices', return_value=devices)
        self.patch.start()
        self.window = MainWindow(load_config(Path('config.yaml')), Path(self.folder.name) / 'devices.json')
        self.wait_until(lambda: not self.window.loading)

    def wait_until(self, predicate):
        end = time.monotonic() + 5
        while not predicate() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(predicate())

    def tearDown(self):
        self.window.close()
        self.wait_until(lambda: all(f.done() for f in self.window.futures))
        self.app.processEvents()
        self.patch.stop()
        self.folder.cleanup()

    def test_cannot_record_before_preparation(self):
        self.assertFalse(self.window.panels['A_TO_B']['button'].isEnabled())
        self.window.initialize()
        self.assertIn('すべて選んで', self.window.status.toPlainText())

    def test_playback_locks_peer_and_device_changes(self):
        self.window.ready = True
        self.window.on_event({'direction': 'A_TO_B', 'state': 'PLAYING'})
        self.assertFalse(self.window.panels['B_TO_A']['button'].isEnabled())
        self.assertFalse(self.window.selectors['mic_a'].isEnabled())
        self.window.on_event({'direction': 'A_TO_B', 'state': 'IDLE'})
        self.assertTrue(self.window.panels['B_TO_A']['button'].isEnabled())

    def test_recording_stop_remains_available(self):
        self.window.ready = True
        self.window.on_event({'direction': 'A_TO_B', 'state': 'RECORDING'})
        self.assertTrue(self.window.panels['A_TO_B']['button'].isEnabled())
        self.assertEqual(self.window.panels['A_TO_B']['button'].text(), 'Stop A Recording')
        self.assertFalse(self.window.panels['B_TO_A']['button'].isEnabled())

    def test_worker_prepares_and_saves_selection(self):
        for role, index in [('mic_a', 1), ('mic_b', 2), ('speaker_a', 1), ('speaker_b', 2)]:
            self.window.selectors[role].setCurrentIndex(index)
        with patch('speech_translator.gui.main_window.load_engines', return_value=(Mock(), Mock(), Mock())), \
                patch('sounddevice.check_input_settings'), patch('sounddevice.check_output_settings'):
            self.window.initialize()
            self.wait_until(lambda: self.window.ready)
        self.assertTrue(self.window.selection_path.exists())
        self.assertEqual(self.window.coordinator.channels['A_TO_B'].output_device, 3)
        self.assertEqual(self.window.coordinator.channels['B_TO_A'].output_device, 2)

    def test_automatic_blocks_manual_until_fully_stopped(self):
        from threading import Event
        self.window.ready = True
        runner = Mock(stopping=Event())
        runner.stop.side_effect = runner.stopping.set
        self.window.automatic = runner
        self.window.coordinator = Mock()
        self.window.coordinator.close.return_value = []
        self.window.update_controls()
        self.assertTrue(self.window.auto_button.isEnabled())
        self.assertFalse(self.window.selectors['mic_a'].isEnabled())
        for direction in self.window.panels:
            self.assertFalse(self.window.panels[direction]['button'].isEnabled())
            self.window.toggle(direction)
        self.window.coordinator.toggle.assert_not_called()
        self.window.on_event({'direction': 'A_TO_B', 'state': 'PLAYING'})
        self.assertTrue(self.window.auto_button.isEnabled())
        self.window.toggle_automatic()
        runner.stop.assert_called_once()
        self.assertFalse(self.window.auto_button.isEnabled())
        self.window.on_event({'direction': 'A_TO_B', 'state': 'IDLE'})
        self.assertFalse(self.window.auto_button.isEnabled())
        self.window.on_automatic_status(False, '停止しました')
        self.assertTrue(self.window.auto_button.isEnabled())
        self.assertTrue(self.window.panels['A_TO_B']['button'].isEnabled())
        self.assertTrue(self.window.selectors['mic_a'].isEnabled())
