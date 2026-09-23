"""TTS adapter with an isolated, persistent inference process."""
import atexit
import base64
import json
import os
import queue
import subprocess
import threading
from pathlib import Path
import numpy as np
from speech_translator.audio.pcm import Audio

class ProcessTTS:
    model_filename = 'model.safetensors'
    worker_filename = 'qwen_worker.py'
    label = 'Qwen3-TTS 0.6B'
    def __init__(self, config, progress=lambda _: None):
        self.config = config
        self.lock = threading.RLock()
        self.responses = queue.Queue()
        self.process = None
        self.log = None
        python = Path(config['python_executable'])
        if not python.is_file() or not (Path(config['model_path']) / self.model_filename).is_file():
            raise FileNotFoundError('TTSの環境またはモデルがありません。READMEのTTS準備手順を実行してください。')
        log_path = Path(config['log_path'])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log = log_path.open('w', encoding='utf-8')
        env = os.environ.copy()
        env.update(PYTHONIOENCODING='utf-8', HF_HUB_OFFLINE='1')
        progress(self.label + ': ロード中')
        try:
            self.process = subprocess.Popen(
                [str(python), '-u', str(Path(__file__).with_name(self.worker_filename)), json.dumps(config)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                text=True, encoding='utf-8', env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.reader = threading.Thread(target=self._read, daemon=True, name='qwen-output')
            self.reader.start()
            result = self._receive()
            if not result.get('ready'):
                raise RuntimeError('TTSの初期化応答が不正です。')
            if config['device'].startswith('cuda') and (not result.get('device', '').startswith('cuda') or not result.get('decoder_device', '').startswith('cuda')):
                raise RuntimeError('TTSのGPU配置を確認できません。')
            self.info = result
            for language in ('ja', 'en'):
                if config[language + '_speaker'].lower() not in [s.lower() for s in result['speakers']]:
                    raise ValueError('TTSの未対応話者: ' + config[language + '_speaker'])
            atexit.register(self.close)
            progress('✓ ' + self.label + ' (日英)')
        except BaseException:
            self.close()
            raise

    def _read(self):
        stream = self.process.stdout
        try:
            for line in stream:
                self.responses.put(json.loads(line))
        except Exception as exc:
            self.responses.put({'error': 'TTS応答の解析に失敗: ' + str(exc)})
        finally:
            self.responses.put({'error': 'TTSワーカーが終了しました。ログを確認してください。'})

    def _receive(self):
        try:
            response = self.responses.get(timeout=self.config['timeout_seconds'])
        except queue.Empty:
            self.close()
            raise TimeoutError('TTSがタイムアウトしました。アプリを再起動してください。')
        if 'error' in response:
            raise RuntimeError('TTS: ' + response['error'])
        return response

    def synthesize(self, text, language):
        if language not in ('ja', 'en') or not text.strip() or len(text) > 2000:
            raise ValueError('TTSの言語またはテキストが不正です。')
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError('TTSが終了しています。アプリを再起動してください。')
            self.process.stdin.write(json.dumps({'op': 'synthesize', 'text': text,
                'language': language, 'speaker': self.config[language + '_speaker']}, ensure_ascii=False) + '\n')
            self.process.stdin.flush()
            result = self._receive()
            self.last_metrics = result.get('cuda', {})
            samples = np.frombuffer(base64.b64decode(result['samples'], validate=True), dtype='<f4').copy()
            audio = Audio(samples, int(result['rate']))
            audio.validate()
            return audio

    def close(self):
        with self.lock:
            if self.process is not None:
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=5)
                for pipe in (self.process.stdin, self.process.stdout):
                    if pipe:
                        pipe.close()
                self.process = None
            if self.log is not None:
                self.log.close()
                self.log = None
