"""Runtime endpoint selection and persisted identities."""

import json
import os
import tempfile
from pathlib import Path

from speech_translator.audio.devices import AudioDevice

ROLES = {'mic_a': 'input_channels', 'mic_b': 'input_channels',
         'speaker_a': 'output_channels', 'speaker_b': 'output_channels'}


def load_selection(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('設定ファイルの形式が不正です。')
    return data


def resolve_saved(saved: object, candidates: list[AudioDevice]) -> AudioDevice | None:
    if not isinstance(saved, dict):
        return None
    matches = [d for d in candidates
               if d.name == saved.get('name') and d.host_api == saved.get('host_api')]
    # An index alone cannot identify an endpoint after reconnecting hardware.
    return matches[0] if len(matches) == 1 else None


def choose_devices(devices: list[AudioDevice], saved: dict, explicit: dict,
                   read=input, write=print) -> dict[str, AudioDevice]:
    selected = {}
    for role, capability in ROLES.items():
        candidates = [d for d in devices if getattr(d, capability) > 0]
        if not candidates:
            raise ValueError(f'{role}: 対応するデバイスがありません。')
        default = resolve_saved(saved.get(role), candidates)
        number = explicit.get(role)
        while True:
            if number is None:
                hint = f' [Enter: {default.index} {default.name}]' if default else ''
                answer = read(f'{role} の番号{hint}: ').strip()
                if not answer and default:
                    number = default.index
                else:
                    try:
                        number = int(answer)
                    except ValueError:
                        write('一覧の番号を入力してください。')
                        continue
            device = next((d for d in candidates if d.index == number), None)
            peer = {'mic_b': 'mic_a', 'speaker_b': 'speaker_a'}.get(role)
            if device is None:
                error = f'{role}: {number} は対応するデバイスではありません。'
            elif peer and selected[peer].index == number:
                error = f'{role}: AとBには別のデバイスを指定してください。'
            else:
                selected[role] = device
                break
            if explicit.get(role) is not None:
                raise ValueError(error)
            write(error)
            number = None
    return selected


def save_selection(path: Path, selected: dict[str, AudioDevice]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            json.dump({role: device.to_dict() for role, device in selected.items()},
                      stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
