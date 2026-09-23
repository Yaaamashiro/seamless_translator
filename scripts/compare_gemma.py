"""Gemma comparison. Explicit CPU/GPU mode; refuses silent GPU fallback."""
import argparse, ctypes, json, math, os, re, secrets, socket, statistics, subprocess, threading, time
from ctypes import wintypes
from pathlib import Path
import requests
from compare_translation import CASES, gpu
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"artifacts"/"gemma-comparison"
class Counters(ctypes.Structure):
 _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ["PeakWorkingSetSize","WorkingSetSize","QuotaPeakPagedPoolUsage","QuotaPagedPoolUsage","QuotaPeakNonPagedPoolUsage","QuotaNonPagedPoolUsage","PagefileUsage","PeakPagefileUsage","PrivateUsage"]]
def memory(pid):
 kernel=ctypes.WinDLL("kernel32",use_last_error=True); psapi=ctypes.WinDLL("psapi",use_last_error=True)
 kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]; kernel.OpenProcess.restype=wintypes.HANDLE
 kernel.CloseHandle.argtypes=[wintypes.HANDLE]
 psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
 handle=kernel.OpenProcess(0x1000|0x10,False,pid)
 if not handle: return None
 try:
  c=Counters(); c.cb=ctypes.sizeof(c)
  if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(c),c.cb): return None
  return {"working_set_mib":c.WorkingSetSize/1048576,"peak_working_set_mib":c.PeakWorkingSetSize/1048576,"private_commit_mib":c.PrivateUsage/1048576}
 finally: kernel.CloseHandle(handle)
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--model",choices=["gemma4-e2b","gemma4-e4b","hy-mt2","qwen3.5"],required=True)
 ap.add_argument("--backend",choices=["cpu","cuda","vulkan"],required=True)
 ap.add_argument("--gpu-layers",default="auto")
 ap.add_argument("--runtime")
 ap.add_argument("--device",default="Vulkan1")
 ap.add_argument("--tensor-placement")
 ap.add_argument("--repeats",type=int,default=2)
 args=ap.parse_args()
 if args.repeats<1: ap.error("repeats must be positive")
 OUT.mkdir(parents=True,exist_ok=True)
 key=args.model+"-"+args.backend
 result={"model":args.model,"backend_requested":args.backend,"backend_observed":"not started","rows":[],"repeats":args.repeats,"context":2048,"temperature":0,"max_tokens":256,"cache_prompt":False,"thinking":False,"mode":"text only; ASR/TTS unloaded","gpu_board_before_mib":gpu()}
 path=OUT/(key+".json")
 def save():
  tmp=path.with_suffix(".tmp")
  tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(path)
 process=None; log=None; thread=None; stop=threading.Event(); samples=[]
 try:
  manifest=json.loads((ROOT/"artifacts"/"translation-comparison"/"gemma-downloads.json").read_text(encoding="utf-8"))
  baseline=json.loads((ROOT/"artifacts"/"translation-comparison"/"downloads.json").read_text(encoding="utf-8"))
  model=next(m for m in manifest["models"]+baseline["models"] if m["name"]==args.model)
  exe=Path(args.runtime).resolve() if args.runtime else next(Path(manifest["runtime"]["directory"]).rglob("llama-server.exe"))
  runtime_env=os.environ.copy()
  if args.backend=="vulkan":
   backend=exe.parent/"vulkan"/"ggml-vulkan.dll"
   runtime_env["GGML_BACKEND_PATH"]=str(backend)
   runtime_env["PATH"]=str(backend.parent)+os.pathsep+runtime_env.get("PATH","")
  result.update({"artifact":model,"runtime_executable":str(exe)})
  device_check=subprocess.run([str(exe),"--list-devices"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=120,creationflags=subprocess.CREATE_NO_WINDOW,cwd=exe.parent,env=runtime_env)
  result["available_devices"]=device_check.stdout+device_check.stderr
  if args.backend=="cuda" and not re.search(r"CUDA\d",result["available_devices"]):
   raise RuntimeError("CUDA unavailable. Refusing CPU fallback for a GPU measurement.")
  if args.backend=="vulkan" and not re.search(re.escape(args.device)+r": NVIDIA GeForce GTX 1650",result["available_devices"]):
   raise RuntimeError("Requested GTX 1650 Vulkan device unavailable; CPU fallback rejected.")
  with socket.socket() as sock:
   sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]
  command=[str(exe),"-m",model["file"],"--host","127.0.0.1","--port",str(port),"-c","2048","--parallel","1","-ngl",str(args.gpu_layers if args.backend!="cpu" else 0),"--device","CUDA0" if args.backend=="cuda" else args.device if args.backend=="vulkan" else "none","-lv","4","--fit-target","256","--cache-ram","0","--ctx-checkpoints","0"]
  if args.tensor_placement:command.extend(["-ot",args.tensor_placement])
  # Keep per-run loopback API credentials out of artifacts.
  token=secrets.token_urlsafe(24)
  result["command"]=command
  env=runtime_env; env["LLAMA_API_KEY"]=token
  session=requests.Session(); session.trust_env=False
  session.headers["Authorization"]="Bearer "+token
  logfile=OUT/(key+"-server.log")
  log=logfile.open("w",encoding="utf-8")
  start=time.perf_counter()
  process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,cwd=exe.parent,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
  result["pid"]=process.pid
  def monitor():
   while not stop.is_set():
    samples.append({"elapsed":time.perf_counter()-start,"gpu_board_mib":gpu(),"process_memory":memory(process.pid)})
    stop.wait(.5)
  thread=threading.Thread(target=monitor,daemon=True); thread.start()
  base=f"http://127.0.0.1:{port}"
  deadline=time.monotonic()+300
  while True:
   if process.poll() is not None: raise RuntimeError(f"server exit {process.returncode}; see {logfile.name}")
   try:
    if session.get(base+"/health",timeout=2).status_code==200: break
   except requests.RequestException: pass
   if time.monotonic()>deadline: raise TimeoutError("server startup")
   time.sleep(.5)
  logtext=logfile.read_text(encoding="utf-8",errors="replace")
  result["allocation_log"]=[line for line in logtext.splitlines() if re.search(r"buffer size|offload|using device|model size|CPU|CUDA|Vulkan",line,re.I)]
  if args.backend!="cpu" and not re.search(r"offloaded [1-9]\d*/\d+ layers to GPU",logtext):
   raise RuntimeError("GPU layer offload not confirmed; refuse GPU label")
  result["backend_observed"]="CPU" if args.backend=="cpu" else args.backend+"; see allocation_log for CPU/GPU split"
  result["load_seconds"]=time.perf_counter()-start
  print("Loaded "+key,flush=True); save()
  def translate(text,source):
   target="English" if source=="ja" else "Japanese"
   prompt=f"Translate the following text into {target}. Note that you should only output the translated result without any additional explanation:\n\n{text}"
   r=session.post(base+"/v1/chat/completions",json={"messages":[{"role":"user","content":prompt}],"temperature":0,"seed":42,"max_tokens":256,"cache_prompt":False,"chat_template_kwargs":{"enable_thinking":False}},timeout=180)
   r.raise_for_status(); body=r.json(); choice=body["choices"][0]
   return {"text":choice["message"].get("content") or "","finish_reason":choice["finish_reason"],"usage":body.get("usage"),"timings":body.get("timings")}
  for source,text in [("ja","こんにちは。"),("en","Hello.")]: translate(text,source)
  for repeat in range(args.repeats):
   for ident,source,text in CASES:
    tick=time.perf_counter()
    try: answer=translate(text,source)
    except Exception as exc: answer={"error":str(exc)}
    row={"id":ident,"source":source,"input":text,"repeat":repeat+1,"seconds":time.perf_counter()-tick,**answer}
    result["rows"].append(row); save()
    print(f"{key} {repeat+1}/{args.repeats} {ident}: {row['seconds']:.2f}s {row.get('text',row.get('error'))}",flush=True)
  good=[r["seconds"] for r in result["rows"] if r.get("text") and r.get("finish_reason")=="stop"]
  result["median_seconds"]=statistics.median(good) if good else None
  result["p95_seconds"]=sorted(good)[math.ceil(len(good)*.95)-1] if good else None
  result["request_failures"]=len(result["rows"])-len(good)
 except Exception as exc:
  result["error"]=str(exc); print(str(exc),flush=True)
 finally:
  stop.set()
  if thread: thread.join(timeout=7)
  result["memory_samples"]=samples
  for label,values in [
   ("gpu_peak_board_mib",[s["gpu_board_mib"] for s in samples if s["gpu_board_mib"] is not None]),
   ("peak_process_working_set_mib",[s["process_memory"]["peak_working_set_mib"] for s in samples if s["process_memory"]]),
   ("peak_process_private_commit_mib",[s["process_memory"]["private_commit_mib"] for s in samples if s["process_memory"]])]:
   result[label]=max(values,default=None)
  result["memory_notes"]="GPU: board total, includes other apps; CPU working set and private commit are separate metrics, not additive. Sample interval >=0.5s."
  if process is not None:
   process.terminate()
   try: process.wait(timeout=15)
   except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
  if log: log.close()
  save()
 if result.get("error"): raise SystemExit(1)
if __name__=="__main__": main()
