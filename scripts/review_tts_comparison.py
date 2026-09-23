"""Transcribe generated comparison WAVs after GPU measurements have finished."""
import hashlib,json,statistics,unicodedata,re
from pathlib import Path
from speech_translator.config import load_config,setup_model_cache
from speech_translator.asr.faster_whisper import FasterWhisperASR
from speech_translator.audio.pcm import Audio
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/tts-comparison'
config=load_config(ROOT/'config.yaml');cache=setup_model_cache(config)
asr=FasterWhisperASR(config['asr'],cache/'whisper')
for name in ['kokoro','qwen']:
 p=OUT/(name+'.json');data=json.loads(p.read_text(encoding='utf-8'))
 for row in data['rows']:
  if row['repeat']<0 or 'error' in row:continue
  audio=Audio.load(OUT/row['wav'])
  row['asr']=asr.transcribe(audio.samples,audio.sample_rate,row['language'])
  print(name,row['id'],row['repeat'],row['asr'],flush=True)
 (OUT/(name+'-reviewed.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
before=json.loads((OUT/'production-before.json').read_text(encoding='utf-8'))
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in before}
changed=[p for p in before if before[p]!=after[p]]
(OUT/'production-verification.json').write_text(json.dumps({'files_checked':len(before),'changed':changed,'after':after},indent=2),encoding='utf-8')
assert not changed,changed
print('Production files unchanged:',len(before),flush=True)
