"""Extract the official Vulkan runtime via a small number of ranged CDN reads."""
import binascii,concurrent.futures,hashlib,io,json,requests,struct,time,zipfile,zlib
from pathlib import Path
URL="https://github.com/ollama/ollama/releases/download/v0.34.2/ollama-windows-amd64.zip"
TOTAL=1460928014
ROOT=Path(".tools/ollama-v0.34.2-vulkan");ROOT.mkdir(parents=True,exist_ok=True)
session=requests.Session()
def request(method,url,**kwargs):
 for attempt in range(5):
  r=session.request(method,url,timeout=(20,90),**kwargs)
  if r.status_code in (429,503):
   delay=max(30,min(120,int(r.headers.get("Retry-After","30"))))
   print(f"Rate limited; waiting {delay}s",flush=True);time.sleep(delay);continue
  r.raise_for_status();return r
 raise RuntimeError("Download service remains rate limited")
resolved=request("HEAD",URL,allow_redirects=True).url
def readrange(start,length):
 end=min(TOTAL,start+length)-1
 r=request("GET",resolved,headers={"Range":f"bytes={start}-{end}"})
 if r.status_code!=206 or r.headers.get("Content-Range")!=f"bytes {start}-{end}/{TOTAL}":raise RuntimeError("Unexpected byte range")
 return r.content
class Remote(io.RawIOBase):
 def __init__(self):self.pos=0
 def seek(self,off,whence=0):self.pos=off if whence==0 else self.pos+off if whence==1 else TOTAL+off;return self.pos
 def tell(self):return self.pos
 def read(self,n=-1):
  if n<0:n=TOTAL-self.pos
  data=readrange(self.pos,n);self.pos+=len(data);return data
with zipfile.ZipFile(Remote()) as z:infos=[i for i in z.infolist() if not i.is_dir() and "/cuda_v" not in i.filename]
def extract(i):
 target=(ROOT/i.filename).resolve()
 if not target.is_relative_to(ROOT.resolve()):raise RuntimeError("Invalid zip path")
 data=target.read_bytes() if target.exists() else b""
 if len(data)!=i.file_size or binascii.crc32(data)!=i.CRC:
  raw=readrange(i.header_offset,i.compress_size+1024)
  namelen,extralen=struct.unpack_from("<HH",raw,26);start=30+namelen+extralen
  compressed=raw[start:start+i.compress_size]
  data=zlib.decompress(compressed,-15) if i.compress_type==8 else compressed
  if len(data)!=i.file_size or binascii.crc32(data)!=i.CRC:raise RuntimeError("ZIP CRC mismatch")
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  print("Extracted "+i.filename,flush=True)
 return {"file":i.filename,"sha256":hashlib.sha256(data).hexdigest(),"size":len(data)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:files=list(pool.map(extract,infos))
(ROOT/"download.json").write_text(json.dumps({"release":"v0.34.2","url":URL,"selection":"Shared files and Vulkan backend; original bytes verified against ZIP CRC; Authenticode verification required","files":files},indent=2),encoding="utf-8")
print("Vulkan runtime ready for signature verification",flush=True)
