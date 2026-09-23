"""Download pinned official Qwen TTS weights and verify SHA256."""
import concurrent.futures,hashlib,json,time
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
REPO="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice";REV="85e237c12c027371202489a0ec509ded67b5e4b5"
DEST=ROOT/"models"/"qwen3-tts-0.6b-customvoice"
def download(item):
 name=item["rfilename"];dest=DEST/name;dest.parent.mkdir(parents=True,exist_ok=True)
 url=f"https://huggingface.co/{REPO}/resolve/{REV}/{name}"
 s=requests.Session();expected=item.get("lfs",{}).get("sha256")
 if not expected:
  r=s.get(url,timeout=60);r.raise_for_status();dest.write_bytes(r.content);return
 if dest.exists():
  with dest.open("rb") as f:
   if hashlib.file_digest(f,"sha256").hexdigest()==expected:return
 part=dest.with_suffix(dest.suffix+".partial");size=item["size"]
 offset=part.stat().st_size if part.exists() else 0
 with part.open("ab") as f:
  while offset<size:
   end=min(offset+16*1024*1024,size)-1
   for attempt in range(4):
    try:
     r=s.get(url+f"?range_start={offset}",headers={"Range":f"bytes={offset}-{end}"},timeout=(20,90));r.raise_for_status()
     if r.status_code!=206 or r.headers.get("Content-Range")!=f"bytes {offset}-{end}/{size}" or len(r.content)!=end-offset+1:raise RuntimeError("Range mismatch")
     break
    except Exception:
     if attempt==3:raise
     time.sleep(3*(attempt+1))
   f.write(r.content);f.flush();offset=end+1
   if offset%(256*1024*1024)==0 or offset==size:print(f"{name}: {offset/size:.0%}",flush=True)
 with part.open("rb") as f:
  if hashlib.file_digest(f,"sha256").hexdigest()!=expected:raise RuntimeError("SHA256 mismatch")
 part.replace(dest);print("Verified "+name,flush=True)
if __name__=="__main__":
 r=requests.get(f"https://huggingface.co/api/models/{REPO}/revision/{REV}?blobs=true",timeout=30);r.raise_for_status()
 items=[i for i in r.json()["siblings"] if i["rfilename"].endswith((".json",".txt",".safetensors"))]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(download,items))
 (DEST/"download.json").write_text(json.dumps({"repo":REPO,"revision":REV,"files":items},indent=2),encoding="utf-8")
 print("Qwen TTS ready",flush=True)
