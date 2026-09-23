import tempfile
import unittest
from pathlib import Path

from speech_translator.audio.devices import AudioDevice
from speech_translator.audio.selection import choose_devices, load_selection, resolve_saved, save_selection


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.devices = [AudioDevice(i, f'Device {i}', 'WASAPI', 2 if i < 2 else 0,
                                    0 if i < 2 else 2, 48000) for i in range(4)]
        self.explicit = dict(mic_a=0, mic_b=1, speaker_a=2, speaker_b=3)

    def test_explicit_selection_and_roundtrip(self):
        chosen = choose_devices(self.devices, {}, self.explicit)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            save_selection(path, chosen)
            saved = load_selection(path)
        self.assertEqual(saved['speaker_b']['index'], 3)
        self.assertEqual(saved['mic_a']['name'], 'Device 0')

    def test_restoration_uses_identity_not_stale_index(self):
        saved = self.devices[0].to_dict()
        moved = AudioDevice(9, 'Device 0', 'WASAPI', 2, 0, 48000)
        self.assertEqual(resolve_saved(saved, [moved]).index, 9)
        self.assertIsNone(resolve_saved(saved, [self.devices[1]]))

    def test_ambiguous_identity_requires_reselection(self):
        duplicate = AudioDevice(9, 'Device 0', 'WASAPI', 2, 0, 48000)
        self.assertIsNone(resolve_saved(self.devices[0].to_dict(), [self.devices[0], duplicate]))

    def test_wrong_direction_rejected(self):
        with self.assertRaisesRegex(ValueError, '対応するデバイス'):
            choose_devices(self.devices, {}, dict(self.explicit, mic_a=2))

    def test_duplicate_device_rejected(self):
        with self.assertRaisesRegex(ValueError, '別のデバイス'):
            choose_devices(self.devices, {}, dict(self.explicit, mic_b=0))

    def test_interactive_invalid_input_then_selection(self):
        answers = iter(['abc', '99', '0', '1', '2', '3'])
        chosen = choose_devices(self.devices, {}, {}, read=lambda _: next(answers), write=lambda _: None)
        self.assertEqual(chosen['mic_a'].index, 0)
        self.assertEqual(chosen['speaker_b'].index, 3)

    def test_enter_accepts_saved_identity(self):
        saved = {role: self.devices[index].to_dict() for role, index in self.explicit.items()}
        chosen = choose_devices(self.devices, saved, {}, read=lambda _: '')
        self.assertEqual(chosen['mic_b'].index, 1)


if __name__ == '__main__':
    unittest.main()
