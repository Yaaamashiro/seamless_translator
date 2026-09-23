"""Download pinned public translation models and official llama.cpp CUDA runtime."""
import concurrent.futures, hashlib, json, os, urllib.request, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.environ["HF_HUB_DISABLE_XET"] = "1"
MODELS = [
 ("hy-mt2", "tencent/Hy-MT2-1.8B-GGUF", "a0c709d9fac510f2c807aa3af52872340dc37a4a", "Hy-MT2-1.8B-Q4_K_M.gguf"),
 ("qwen3.5", "unsloth/Qwen3.5-2B-GGUF", "f6d5376be1edb4d416d56da11e5397a961aca8ae", "Qwen3.5-2B-Q4_K_M.gguf"),
]
def model(item):
 from huggingface_hub import hf_hub_download
 name, repo, revision, filename = item
 print("Downloading " + name, flush=True)
 path = hf_hub_download(repo, filename, revision=revision, local_dir=ROOT/"models"/"translation"/name)
 print("Ready " + name, flush=True)
 return dict(name=name, repo=repo, revision=revision, file=str(path))
def runtime():
 tag = "b10964"
 dest = ROOT/".tools"/("llama-"+tag)
 dest.mkdir(parents=True, exist_ok=True)
 with urllib.request.urlopen("https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/"+tag) as r:
  release = json.load(r)
 for name in [f"llama-{tag}-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip"]:
  asset = next(x for x in release["assets"] if x["name"] == name)
  archive = dest/name
  if not archive.exists() or archive.stat().st_size != asset["size"]:
   print("Downloading "+name, flush=True)
   urllib.request.urlretrieve(asset["browser_download_url"], archive)
  digest = asset.get("digest")
  if digest and digest.startswith("sha256:"):
   actual = hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()
   if actual != digest.split(":")[1]: raise RuntimeError("Checksum mismatch "+name)
  with zipfile.ZipFile(archive) as z:
   for member in z.infolist():
    if not (dest/member.filename).resolve().is_relative_to(dest.resolve()): raise RuntimeError("Invalid zip")
   z.extractall(dest)
 print("Ready runtime", flush=True)
 return dict(tag=tag, directory=str(dest))
if __name__ == "__main__":
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  tasks = [pool.submit(model, m) for m in MODELS]
  rt = pool.submit(runtime)
  result = dict(models=[f.result() for f in tasks], runtime=rt.result())
 out=ROOT/"artifacts"/"translation-comparison"
 out.mkdir(parents=True, exist_ok=True)
 (out/"downloads.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
