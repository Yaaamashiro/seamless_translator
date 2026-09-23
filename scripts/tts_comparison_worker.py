import contextlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/tts-comparison';name=sys.argv[1]
torch.set_num_threads(2)
assert torch.cuda.is_available(), 'CUDA required'
cases=json.loads((OUT/'cases.json').read_text(encoding='utf-8-sig'));rows=[];started=time.perf_counter()
with contextlib.redirect_stdout(sys.stderr):
 if name=='qwen':
  from qwen_tts import Qwen3TTSModel
  sys.path.insert(0,str(ROOT/'src/speech_translator/tts'))
  from qwen_runtime import stabilize_fp16,bounded_generate
  model=Qwen3TTSModel.from_pretrained(str(ROOT/'models/qwen3-tts-0.6b-customvoice'),device_map='cuda:0',dtype=torch.float16,attn_implementation='sdpa')
  stabilize_fp16(model);model.model.speech_tokenizer.model.encoder.to('cpu');model.model.generate=bounded_generate(model.model.generate)
  device=str(next(model.model.talker.parameters()).device)
  def synth(text,lang):
   waves,rate=model.generate_custom_voice(text=text,language={'ja':'Japanese','en':'English'}[lang],speaker={'ja':'ono_anna','en':'ryan'}[lang],max_new_tokens=1024)
   return np.asarray(waves[0],dtype=np.float32),rate,None
 else:
  from kokoro import KModel,KPipeline
  folder=ROOT/'models/kokoro-comparison'
  model=KModel(repo_id='hexgrad/Kokoro-82M',config=str(folder/'config.json'),model=str(folder/'kokoro-v1_0.pth')).to('cuda:0').eval()
  pipes={lang:KPipeline(lang_code=code,model=model,repo_id='hexgrad/Kokoro-82M',device='cuda:0') for lang,code in [('ja','j'),('en','a')]}
  voices={lang:torch.load(folder/'voices'/voice,map_location='cpu',weights_only=True) for lang,voice in [('ja','jf_alpha.pt'),('en','af_heart.pt')]}
  device=str(next(model.parameters()).device)
  def synth(text,lang):
   chunks=list(pipes[lang](text,voice=voices[lang],speed=1))
   return np.concatenate([x.audio.cpu().numpy() for x in chunks]),24000,' / '.join(x.phonemes for x in chunks)
assert device.startswith('cuda'),device
load_seconds=time.perf_counter()-started
print(json.dumps({'model':name,'loaded_seconds':load_seconds,'device':device}),flush=True)
for repeat in [-1,0,1]:
 selected=[{'id':'warm-ja','language':'ja','text':'こんにちは。'},{'id':'warm-en','language':'en','text':'Hello.'}] if repeat<0 else cases
 for case in selected:
  row={**case,'repeat':repeat,'seed':42+max(0,repeat)}
  try:
   torch.manual_seed(row['seed']);torch.cuda.empty_cache();torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();tick=time.perf_counter()
   with torch.inference_mode(),contextlib.redirect_stdout(sys.stderr):audio,rate,phonemes=synth(case['text'],case['language'])
   torch.cuda.synchronize()
   row.update(seconds=time.perf_counter()-tick,audio_seconds=len(audio)/rate,allocated_peak_mib=torch.cuda.max_memory_allocated()/1048576,reserved_peak_mib=torch.cuda.max_memory_reserved()/1048576)
   if not len(audio) or not np.isfinite(audio).all() or np.sqrt(np.mean(audio.astype('float64')**2))<.0001:raise RuntimeError('Invalid/silent audio')
   row['rtf']=row['seconds']/row['audio_seconds'];row['wav']=f'{name}-{case["id"]}-{repeat}.wav'
   if phonemes:row['phonemes']=phonemes
   sf.write(OUT/row['wav'],audio,rate,subtype='PCM_16')
  except Exception as exc:row['error']=str(exc);traceback.print_exc(file=sys.stderr)
  rows.append(row)
  (OUT/(name+'.json')).write_text(json.dumps({'model':name,'device':device,'torch':torch.__version__,'gpu':torch.cuda.get_device_name(0),'load_seconds':load_seconds,'rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps(row,ensure_ascii=False),flush=True)
  if 'error' in row and 'CUDA' in row['error']:raise SystemExit(1)
