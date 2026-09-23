"""Download official pinned Gemma GGUF using resumable ranges and SHA256."""
import concurrent.futures, hashlib, json, time
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"artifacts"/"translation-comparison"
PINS={"E2B":"675cff42a74c774d6cb76f76d8eacb49b48c9b93","E4B":"4b4a2c1d584be7264f87aac328a1bc739ce81b6c"}
def download(size):
 repo=f"google/gemma-4-{size}-it-qat-q4_0-gguf"; revision=PINS[size]
 name="gemma4-"+size.lower(); filename=f"gemma-4-{size}_q4_0-it.gguf"
 session=requests.Session()
 r=session.get(f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true",timeout=30); r.raise_for_status(); info=r.json()
 if info.get("gated"): raise RuntimeError("Access restricted")
 item=next(x for x in info["siblings"] if x["rfilename"]==filename)
 total=item["lfs"]["size"]; expected=item["lfs"]["sha256"]
 dest=ROOT/"models"/"translation"/name/filename; dest.parent.mkdir(parents=True,exist_ok=True)
 partial=dest.with_suffix(".gguf.partial")
 if not dest.exists():
  offset=partial.stat().st_size if partial.exists() else 0
  if offset>total: raise RuntimeError("Oversize partial file")
  url=f"https://huggingface.co/{repo}/resolve/{revision}/{filename}"
  with partial.open("ab") as f:
   while offset<total:
    end=min(offset+16*1024*1024,total)-1
    for attempt in range(4):
     try:
      # Distinct query prevents upstream caches reusing another byte range.
      with session.get(url+f"?download=true&range_start={offset}",headers={"Range":f"bytes={offset}-{end}"},timeout=(20,60)) as response:
       response.raise_for_status()
       if response.status_code!=206 or response.headers.get("Content-Range")!=f"bytes {offset}-{end}/{total}": raise RuntimeError("Incorrect range response")
       chunk=response.content
       if len(chunk)!=end-offset+1: raise RuntimeError("Incorrect chunk size")
      break
     except Exception:
      if attempt==3: raise
      time.sleep(2*(attempt+1))
    f.write(chunk); f.flush(); offset+=len(chunk)
    if offset%(256*1024*1024)==0 or offset==total: print(f"{size}: {offset/total:.0%} ({offset/1e9:.2f}/{total/1e9:.2f} GB)",flush=True)
  with partial.open("rb") as f: actual=hashlib.file_digest(f,"sha256").hexdigest()
  if actual!=expected: raise RuntimeError("SHA256 mismatch "+size)
  partial.replace(dest)
 else:
  with dest.open("rb") as f: actual=hashlib.file_digest(f,"sha256").hexdigest()
  if actual!=expected: raise RuntimeError("SHA256 mismatch "+size)
 print(size+" verified",flush=True)
 return {"name":name,"repo":repo,"revision":revision,"file":str(dest),"quantization":"QAT Q4_0","size_bytes":total,"sha256":expected}
if __name__=="__main__":
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: models=list(pool.map(download,["E2B","E4B"]))
 runtime=json.loads((OUT/"downloads.json").read_text(encoding="utf-8"))["runtime"]
 (OUT/"gemma-downloads.json").write_text(json.dumps({"models":models,"runtime":runtime},indent=2),encoding="utf-8")
 print("Gemma downloads complete",flush=True)
