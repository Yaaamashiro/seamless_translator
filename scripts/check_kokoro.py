"""Real GPU integration check, with file output instead of loudspeaker playback."""
import json,time,threading,subprocess
from pathlib import Path
from speech_translator.config import load_config
from speech_translator.pipeline.engines import load_engines,close_engines
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"artifacts"/"kokoro-check";OUT.mkdir(parents=True,exist_ok=True)
config=load_config(ROOT/"config.yaml")
rows=[];samples=[];metadata={};stop=threading.Event()
def monitor():
 while not stop.is_set():
  try:
   p=subprocess.run(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
   samples.append(int(p.stdout.strip().splitlines()[0]))
  except Exception:pass
  stop.wait(.5)
thread=threading.Thread(target=monitor,daemon=True);thread.start()
engines=()
try:
 tick=time.perf_counter();engines=load_engines(config,lambda s:print(s,flush=True))
 metadata.update(load_seconds=time.perf_counter()-tick, translation_gpu_layers=config['translation']['gpu_layers'], tts=engines[2].info)
 print('Load seconds',metadata['load_seconds'],flush=True)
 for source,target,text in [("ja","en","駅はどこですか？"),("en","ja","Let us meet at the reception desk on the second floor at 3 p.m. tomorrow.")]:
  row={"source":source,"target":target,"input":text}
  tick=time.perf_counter();translated=engines[1].translate(text,source,target)
  row.update(translation=translated,translation_seconds=time.perf_counter()-tick)
  print("Translation",translated,flush=True)
  tick=time.perf_counter();audio=engines[2].synthesize(translated,target)
  row.update(cuda=engines[2].last_metrics,tts_seconds=time.perf_counter()-tick,audio_seconds=audio.duration,sample_rate=audio.sample_rate)
  audio.save(OUT/(source+"-to-"+target+".wav"))
  row["asr_of_generated_audio"]=engines[0].transcribe(audio.samples,audio.sample_rate,target)
  rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
finally:
 stop.set();thread.join(timeout=6);close_engines(engines)
 (OUT/"results.json").write_text(json.dumps({"configuration":metadata,"rows":rows,"gpu_peak_board_mib":max(samples,default=None),"gpu_samples":samples,"note":"Models concurrently loaded; generated WAV validated and transcribed; physical microphone/playback not tested"},ensure_ascii=False,indent=2),encoding="utf-8")
