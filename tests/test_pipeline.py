import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np

from speech_translator.audio.devices import AudioDevice
from speech_translator.audio.pcm import Audio
from speech_translator.config import load_config
from speech_translator.pipeline.channel import ChannelState
from speech_translator.pipeline.coordinator import Coordinator, build_channels
from speech_translator.logging.session_logger import SessionLogger


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(Path('config.yaml'))
        self.asr, self.mt, self.tts = Mock(), Mock(), Mock()
        self.asr.transcribe.return_value = 'hello'
        self.mt.translate.return_value = 'こんにちは'
        self.audio = Audio(np.full(1600, .1, dtype='float32'), 16000)
        self.tts.synthesize.return_value = self.audio
        selected = {role: AudioDevice(i, role, 'test', 2, 2, 48000)
                    for i, role in enumerate(['mic_a', 'mic_b', 'speaker_a', 'speaker_b'])}
        self.events = []
        self.logger = Mock()
        self.channels = build_channels(selected, (self.asr, self.mt, self.tts), self.config,
                                       self.logger, self.events.append)
        for channel in self.channels.values():
            channel.recorder = Mock()
            channel.player = Mock()
            channel.player.play.side_effect = lambda audio, on_start: on_start()

    def tearDown(self):
        for channel in self.channels.values():
            channel.close().result()

    def test_both_routes_languages_and_repeated_utterances(self):
        for key, input_id, output_id, source, target in [
                ('A_TO_B', 0, 3, 'ja', 'en'), ('B_TO_A', 1, 2, 'en', 'ja')] * 2:
            channel = self.channels[key]
            result = channel.process(self.audio)
            self.assertEqual((channel.input_device, channel.output_device), (input_id, output_id))
            self.assertEqual(result['source_language'], source)
            self.assertEqual(result['target_language'], target)
            self.assertGreaterEqual(result['total_latency_sec'], result['tts_latency_sec'])
            self.assertEqual(channel.state, ChannelState.IDLE)
        self.assertEqual(self.logger.write.call_count, 4)

    def test_empty_recognition_never_translates_or_plays(self):
        self.asr.transcribe.return_value = ' '
        channel = self.channels['A_TO_B']
        self.assertIsNone(channel.process(self.audio))
        self.assertEqual(channel.state, ChannelState.ERROR)
        self.mt.translate.assert_not_called()
        channel.player.play.assert_not_called()

    def test_engine_failure_can_recover(self):
        channel = self.channels['A_TO_B']
        self.mt.translate.side_effect = RuntimeError('out of memory')
        self.assertIsNone(channel.process(self.audio))
        self.mt.translate.side_effect = None
        self.assertIsNotNone(channel.process(self.audio))
        self.assertEqual(channel.state, ChannelState.IDLE)

    def test_echo_guard_blocks_peer(self):
        a, b = self.channels.values()
        b.toggle = Mock()
        coordinator = Coordinator(self.channels)
        for state in [ChannelState.RECORDING, ChannelState.PROCESSING, ChannelState.PLAYING]:
            a.state = state
            coordinator.toggle('B_TO_A')
        b.toggle.assert_not_called()
        a.state = ChannelState.IDLE
        coordinator.toggle('B_TO_A')
        b.toggle.assert_called_once()

    def test_cancel_before_inference(self):
        channel = self.channels['A_TO_B']
        channel.cancelled.set()
        self.assertIsNone(channel.process(self.audio))
        self.asr.transcribe.assert_not_called()

    def test_recordings_are_not_saved_by_default(self):
        self.audio.save = Mock()
        self.channels['A_TO_B'].process(self.audio)
        self.audio.save.assert_not_called()

    def test_disabled_logger_creates_no_files(self):
        with tempfile.TemporaryDirectory() as folder:
            logger = SessionLogger(Path(folder) / 'logs', enabled=False)
            logger.write({'asr_text': 'test'})
            self.assertFalse(logger.path.parent.exists())
