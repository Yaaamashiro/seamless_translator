"""Real-model integration using generated speech, without physical playback."""
import json
from pathlib import Path

from speech_translator.config import load_config
from speech_translator.pipeline.engines import load_engines
from speech_translator.pipeline.channel import Channel
from speech_translator.logging.session_logger import SessionLogger


class FilePlayer:
    def __init__(self, path):
        self.path = path

    def play(self, audio, on_start):
        audio.validate()
        on_start()
        audio.save(self.path)

    def cancel(self):
        pass


config = load_config(Path('config.yaml'))
engines = load_engines(config)
root = Path('artifacts/model-check')
root.mkdir(parents=True, exist_ok=True)
logger = SessionLogger(root)
records = []
for side, source, target, text in [('A', 'ja', 'en', 'こんにちは。今日は沖縄から来ました。'),
                                   ('B', 'en', 'ja', 'Nice to meet you.')]:
    audio = engines[2].synthesize(text, source)
    audio.save(root / f'{side}_source.wav')
    channel = Channel(f'{side}_MODEL_CHECK', -1, -1, source, target, *engines, config, logger,
                      player=FilePlayer(root / f'{side}_translated.wav'))
    try:
        record = channel.process(audio)
        if record is None:
            raise RuntimeError(f'{side} pipeline failed: inspect {logger.path}')
        record['playback_verification'] = 'file output only; total latency is time to file sink'
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    finally:
        channel.close().result()
(root / 'results.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
