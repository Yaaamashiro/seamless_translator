"""Real VAD/ASR/Gemma/Kokoro with simulated microphone input and file playback."""
import json,time,threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from speech_translator.config import load_config
from speech_translator.audio.pcm import Audio
from speech_translator.pipeline.engines import load_engines,close_engines
from speech_translator.pipeline.channel import Channel
from speech_translator.pipeline.automatic import AutomaticConversation
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/automatic-check';OUT.mkdir(parents=True,exist_ok=True)
config=load_config(ROOT/'config.yaml');records=[];statuses=[];streams={};echo_frames=0
class Logger:
 def write(self,record):records.append(record);print(json.dumps(record,ensure_ascii=False),flush=True)
class Stream:
 def __init__(self,device,callback,**kwargs):self.device=device;self.callback=callback;self.active=False;streams[device]=self
 def start(self):self.active=True
 def abort(self):self.active=False
 def close(self):self.active=False
 def push(self,pcm):self.callback(pcm[:,None],len(pcm),SimpleNamespace(currentTime=1,inputBufferAdcTime=1),False)
class FilePlayer:
 def __init__(self,name):self.name=name
 def cancel(self):pass
 def play(self,audio,on_start):
  global echo_frames
  on_start();audio.save(OUT/(self.name+'.wav'))
  echo=audio.resampled(16000).samples
  for start in range(0,len(echo),1600):
   for stream in streams.values():stream.push(echo[start:start+1600]);echo_frames+=1
  assert not auto.accepting.is_set()
  assert auto.queue.empty(),'Playback echo was queued'
def wait_for(predicate,seconds=120):
 deadline=time.monotonic()+seconds
 while not predicate() and time.monotonic()<deadline:
  if auto.future.done():auto.future.result();raise RuntimeError(str(statuses[-1]))
  time.sleep(.02)
 if not predicate():raise TimeoutError(str(statuses[-3:]))
def feed(device,path):
 audio=Audio.load(path).resampled(16000)
 pcm=np.concatenate((np.zeros(8000,dtype='float32'),audio.samples,np.zeros(24000,dtype='float32')))
 for start in range(0,len(pcm),1600):streams[device].push(pcm[start:start+1600]);time.sleep(.012)
engines=load_engines(config);channels={};auto=None
try:
 for direction,device,source,target in [('A_TO_B',101,'ja','en'),('B_TO_A',102,'en','ja')]:
  channels[direction]=Channel(direction,device,-1,source,target,*engines,config,Logger(),player=FilePlayer(direction))
 def notify(running,message):statuses.append((running,message));print(message,flush=True)
 auto=AutomaticConversation(channels,config,notify)
 with patch('speech_translator.pipeline.automatic.sd.InputStream',Stream),patch('speech_translator.pipeline.automatic.sd.query_devices',return_value={'default_samplerate':16000,'max_input_channels':1}):
  auto.start();wait_for(auto.accepting.is_set)
  feed(101,ROOT/'artifacts/kokoro-check/en-to-ja.wav')
  wait_for(lambda:len(records)>=1 and auto.accepting.is_set())
  feed(102,ROOT/'artifacts/kokoro-check/ja-to-en.wav')
  wait_for(lambda:len(records)>=2 and auto.accepting.is_set())
  time.sleep(.8)
  assert len(records)==2,records
  assert all('error' not in r for r in records),records
  assert [r['direction'] for r in records]==['A_TO_B','B_TO_A']
finally:
 if auto:
  auto.stop()
  if auto.future:auto.future.result(timeout=120)
 for c in channels.values():c.close().result(timeout=120)
 close_engines(engines)
 (OUT/'results.json').write_text(json.dumps({'records':records,'statuses':statuses,'echo_callback_blocks_discarded':echo_frames,'note':'Real neural models; simulated mic callbacks and file playback. Physical microphone/speaker acceptance not tested.'},ensure_ascii=False,indent=2),encoding='utf-8')
