from pathlib import Path
import hashlib,json,requests
root=Path(__file__).resolve().parents[1]
out=root/'artifacts/tts-comparison'
repo='hexgrad/Kokoro-82M'
revision='f3ff3571791e39611d31c381e3a41a3af07b4987'
s=requests.Session();r=s.get('https://huggingface.co/api/models/'+repo+'/revision/'+revision+'?blobs=true',timeout=30);r.raise_for_status();info=r.json();rev=info['sha']
files=['config.json','kokoro-v1_0.pth','voices/af_heart.pt','voices/jf_alpha.pt']
dest=root/'models/kokoro-82m';dest.mkdir(parents=True,exist_ok=True);manifest={'repo':repo,'revision':rev,'files':[]}
for name in files:
 item=next(x for x in info['siblings'] if x['rfilename']==name)
 p=dest/name;p.parent.mkdir(parents=True,exist_ok=True)
 expected=item.get('lfs',{}).get('sha256')
 if not p.exists():
  with s.get(f'https://huggingface.co/{repo}/resolve/{rev}/{name}',stream=True,timeout=(20,120)) as response:
   response.raise_for_status()
   with p.with_suffix(p.suffix+'.partial').open('wb') as f:
    for b in response.iter_content(1024*1024):f.write(b)
  p.with_suffix(p.suffix+'.partial').replace(p)
 sha=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected and sha!=expected:raise RuntimeError('Hash mismatch '+name)
 manifest['files'].append({'file':name,'sha256':sha,'size':p.stat().st_size})
 print(name,p.stat().st_size,flush=True)
(dest/'download.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
