import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from speech_translator.audio.pcm import Audio
from speech_translator.audio.recorder import Recorder
from speech_translator.audio.player import Player


class AudioTests(unittest.TestCase):
    def test_resampling_duration_and_wav(self):
        audio = Audio(np.sin(np.arange(4800) * .1).astype('float32'), 48000)
        converted = audio.resampled(16000)
        self.assertEqual(len(converted.samples), 1600)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.wav'
            converted.save(path)
            restored = Audio.load(path)
        self.assertAlmostEqual(restored.duration, .1)

    def test_silence_empty_nonfinite(self):
        for samples in [[], [0, 0], [float('nan')]]:
            with self.assertRaises(ValueError):
                Audio(np.array(samples, dtype='float32'), 16000).validate()

    @patch('speech_translator.audio.recorder.sd')
    def test_recording_buffers_are_separate(self, sd):
        sd.query_devices.return_value = {'default_samplerate': 48000, 'max_input_channels': 2}
        recorder = Recorder(25)
        for value in [.1, .2]:
            recorder.start()
            recorder._callback(np.full((100, 2), value), 100, None, None)
            audio = recorder.stop()
            self.assertEqual(len(audio.samples), 100)
            self.assertAlmostEqual(float(audio.samples.mean()), value)
        self.assertEqual(sd.InputStream.call_args.kwargs['device'], 25)

    @patch('speech_translator.audio.player.sd')
    def test_explicit_output_and_native_rate(self, sd):
        sd.query_devices.return_value = {'default_samplerate': 48000, 'max_output_channels': 2}
        sd.OutputStream.return_value.__enter__.return_value.write.return_value = False
        started = Mock()
        Player(20).play(Audio(np.full(1600, .1, dtype='float32'), 16000), started)
        self.assertEqual(sd.OutputStream.call_args.kwargs['device'], 20)
        self.assertEqual(sd.OutputStream.call_args.kwargs['samplerate'], 48000)
        started.assert_called_once()
