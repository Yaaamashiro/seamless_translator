import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

from speech_translator.audio.devices import DeviceDiscoveryError, format_devices, list_devices
from speech_translator.main import main


class DeviceTests(unittest.TestCase):
    def backend(self):
        backend = Mock()
        backend.query_hostapis.return_value = [{'name': 'Windows WASAPI'}]
        backend.query_devices.return_value = [
            {'name': 'マイクA', 'hostapi': 0, 'max_input_channels': 2,
             'max_output_channels': 0, 'default_samplerate': 48000},
            {'name': 'Speaker B', 'hostapi': 0, 'max_input_channels': 0,
             'max_output_channels': 2, 'default_samplerate': 96000},
        ]
        return backend

    def test_indices_and_native_rates_are_preserved(self):
        devices = list_devices(self.backend())
        self.assertEqual(devices[0].index, 0)
        self.assertEqual(devices[0].name, 'マイクA')
        self.assertEqual(devices[1].index, 1)
        self.assertEqual(devices[1].default_sample_rate, 96000)
        self.assertEqual(devices[0].host_api, 'Windows WASAPI')

    def test_input_output_are_separated(self):
        text = format_devices(list_devices(self.backend()))
        inputs, outputs = text.split('Output Devices')
        self.assertIn('マイクA', inputs)
        self.assertNotIn('Speaker B', inputs)
        self.assertIn('Speaker B', outputs)
        self.assertNotIn('マイクA', outputs)

    def test_backend_failure_has_actionable_error(self):
        backend = self.backend()
        backend.query_devices.side_effect = RuntimeError('disconnected')
        with self.assertRaisesRegex(DeviceDiscoveryError, 'Windows.*disconnected'):
            list_devices(backend)

    def test_empty_list_is_visible(self):
        self.assertEqual(format_devices([]).count('(none)'), 2)

    def test_cli_returns_failure_without_devices(self):
        with patch('speech_translator.main.list_devices', return_value=[]), \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(main(['--list-devices']), 1)

    def test_cli_returns_failure_on_backend_error(self):
        with patch('speech_translator.main.list_devices', side_effect=DeviceDiscoveryError('failure')), \
                redirect_stderr(StringIO()):
            self.assertEqual(main(['--list-devices']), 1)


if __name__ == '__main__':
    unittest.main()
