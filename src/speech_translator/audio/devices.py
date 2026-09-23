"""Enumerate endpoints without opening microphones or changing defaults."""

from dataclasses import asdict, dataclass


class DeviceDiscoveryError(RuntimeError):
    """The audio backend could not enumerate devices."""


@dataclass(frozen=True)
class AudioDevice:
    index: int
    name: str
    host_api: str
    input_channels: int
    output_channels: int
    default_sample_rate: float

    def to_dict(self) -> dict:
        return asdict(self)


def list_devices(backend=None) -> list[AudioDevice]:
    """Return PortAudio endpoints; never interpret indices as physical identity."""
    try:
        if backend is None:
            import sounddevice as backend
        host_apis = backend.query_hostapis()
        devices = backend.query_devices()
        return [
            AudioDevice(
                index=index,
                name=str(device['name']),
                host_api=str(host_apis[device['hostapi']]['name']),
                input_channels=int(device['max_input_channels']),
                output_channels=int(device['max_output_channels']),
                default_sample_rate=float(device['default_samplerate']),
            )
            for index, device in enumerate(devices)
        ]
    except Exception as exc:
        raise DeviceDiscoveryError(
            f'音声デバイスを取得できません。Windowsのサウンド設定と接続を確認してください: {exc}'
        ) from exc


def format_devices(devices: list[AudioDevice]) -> str:
    lines = []
    for title, attribute in [('Input Devices', 'input_channels'), ('Output Devices', 'output_channels')]:
        lines.append(title)
        matching = [device for device in devices if getattr(device, attribute) > 0]
        if not matching:
            lines.append('  (none)')
        for device in matching:
            lines.append(
                f'  {device.index}: {device.name} [{device.host_api}] '
                f'channels={getattr(device, attribute)} '
                f'default_rate={device.default_sample_rate:g} Hz'
            )
        lines.append('')
    lines.append('同じ機器が複数のホストAPIに表示される場合があります。番号は再接続等で変化します。')
    return '\n'.join(lines)
