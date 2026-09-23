import json,os,subprocess,threading,time
from pathlib import Path
from speech_translator.config import load_config
from speech_translator.pipeline.engines import create_translator,close_engines
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/tts-comparison'
config=load_config(ROOT/'config.yaml');config['translation']['log_path']=str(OUT/'gemma.log')
mt=create_translator(config)
try:
 for name in ['kokoro','qwen']:
  samples=[];stop=threading.Event()
  def monitor():
   while not stop.is_set():
    try:
     r=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
     samples.append({'time':time.time(),'mib':int(r.stdout.strip())})
    except Exception:pass
    stop.wait(.5)
  thread=threading.Thread(target=monitor,daemon=True);thread.start()
  env=os.environ.copy();env.update(PYTHONIOENCODING='utf-8',HF_HUB_OFFLINE='1')
  log=(OUT/(name+'-worker.log')).open('w',encoding='utf-8');print('RUN',name,flush=True)
  try:
   with subprocess.Popen([str(ROOT/f'.venv-{name}/Scripts/python.exe'),'-u',str(ROOT/'scripts/tts_comparison_worker.py'),name],cwd=ROOT,env=env,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW) as p:
    try:code=p.wait(timeout=1200)
    except BaseException:p.kill();p.wait();raise
   print('EXIT',name,code,flush=True)
  finally:
   stop.set();thread.join(timeout=6);log.close()
   (OUT/(name+'-gpu.json')).write_text(json.dumps({'gemma_gpu_layers':config['translation']['gpu_layers'],'peak_board_mib':max((x['mib'] for x in samples),default=None),'samples':samples},indent=2),encoding='utf-8')
finally:close_engines((mt,))
