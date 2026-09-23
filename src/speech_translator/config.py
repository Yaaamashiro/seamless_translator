import os
from copy import deepcopy
from pathlib import Path

import yaml

DEFAULTS = {
    'audio': {'sample_rate': 16000, 'max_recording_seconds': 120},
    'automatic': {'threshold': 0.6, 'start_ms': 96, 'min_speech_ms': 256,
                  'silence_ms': 704, 'pre_roll_ms': 320, 'playback_guard_ms': 600,
                  'max_utterance_seconds': 20},
    'asr': {'engine': 'faster-whisper', 'model': 'small', 'device': 'cpu', 'compute_type': 'int8'},
    'translation': {'engine': 'gemma4',
                    'model_path': 'models/translation/gemma4-e4b/gemma-4-E4B_q4_0-it.gguf',
                    'executable': '.tools/ollama-v0.34.2-vulkan/lib/ollama/llama-server.exe',
                    'gpu_device': 'Vulkan1', 'gpu_layers': 8, 'context_size': 2048,
                    'timeout_seconds': 180, 'log_path': 'logs/gemma-runtime.log',
                    'ja_en_model': 'Helsinki-NLP/opus-mt-ja-en',
                    'en_ja_model': 'Helsinki-NLP/opus-tatoeba-en-ja'},
    'tts': {'engine': 'kokoro',
            'model_path': 'models/kokoro-82m',
            'python_executable': '.venv-kokoro/Scripts/python.exe',
            'device': 'cuda:0', 'dtype': 'float32',
            'ja_speaker': 'jf_alpha', 'en_speaker': 'af_heart',
            'max_new_tokens': 1024, 'timeout_seconds': 300, 'log_path': 'logs/kokoro-runtime.log',
            'ja_engine': 'openjtalk', 'en_engine': 'piper', 'en_voice': 'en_US-lessac-medium'},
    'application': {'model_directory': 'models', 'save_logs': True, 'log_directory': 'logs'},
    'debug': {'save_recordings': False, 'recording_directory': 'debug_audio', 'verbose': False},
}


def load_config(path: Path):
    config = deepcopy(DEFAULTS)
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        if not isinstance(data, dict):
            raise ValueError('config.yaml は辞書形式で指定してください。')
        for section, settings in data.items():
            if section not in config or not isinstance(settings, dict):
                raise ValueError(f'不正な設定セクション: {section}')
            unknown = set(settings) - set(config[section])
            if unknown:
                raise ValueError(f'未対応の設定: {section}.{", ".join(unknown)}')
            config[section].update(settings)
    for key in ('sample_rate', 'max_recording_seconds'):
        value = config['audio'][key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f'audio.{key} は正の整数で指定してください。')
    for section, key in [('application', 'save_logs'), ('debug', 'save_recordings'), ('debug', 'verbose')]:
        if not isinstance(config[section][key], bool):
            raise ValueError(f'{section}.{key} はtrue/falseで指定してください。')
    automatic = config['automatic']
    if isinstance(automatic['threshold'], bool) or not isinstance(automatic['threshold'], (int, float)) or not 0 < automatic['threshold'] < 1:
        raise ValueError('automatic.threshold は0より大きく1未満で指定してください。')
    for key in ('start_ms', 'min_speech_ms', 'silence_ms', 'pre_roll_ms', 'playback_guard_ms', 'max_utterance_seconds'):
        value = automatic[key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f'automatic.{key} は正の整数で指定してください。')
    if not (automatic['start_ms'] <= automatic['min_speech_ms'] < automatic['max_utterance_seconds'] * 1000 and
            automatic['silence_ms'] < automatic['max_utterance_seconds'] * 1000):
        raise ValueError('自動発話の開始・最短・無音・最長時間の関係が不正です。')
    if config['translation']['engine'] not in ('gemma4', 'opus'):
        raise ValueError('translation.engine はgemma4またはopusを指定してください。')
    if config['tts']['engine'] not in ('kokoro', 'qwen3', 'legacy'):
        raise ValueError('tts.engine はkokoro、qwen3またはlegacyを指定してください。')
    for section, keys in [('translation', ('gpu_layers', 'context_size', 'timeout_seconds')),
                          ('tts', ('max_new_tokens', 'timeout_seconds'))]:
        for key in keys:
            value = config[section][key]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f'{section}.{key} は正の整数で指定してください。')
    if config['tts']['device'] not in ('cuda:0', 'cpu') or config['tts']['dtype'] not in ('float16', 'float32'):
        raise ValueError('TTSのdevice/dtype設定が不正です。')
    if config['tts']['engine'] == 'kokoro' and config['tts']['dtype'] != 'float32':
        raise ValueError('Kokoroのdtypeはfloat32を指定してください。')
    for section, key in [('translation', 'model_path'), ('translation', 'executable'),
                         ('translation', 'log_path'), ('tts', 'model_path'),
                         ('tts', 'python_executable'), ('tts', 'log_path')]:
        config[section][key] = str((path.resolve().parent / config[section][key]).resolve())
    for section, key in [('application', 'model_directory'), ('application', 'log_directory'),
                         ('debug', 'recording_directory')]:
        config[section][key] = str((path.resolve().parent / config[section][key]).resolve())
    return config


def setup_model_cache(config):
    root = Path(config['application']['model_directory'])
    root.mkdir(parents=True, exist_ok=True)
    os.environ['HF_HOME'] = str(root / 'huggingface')
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    return root
