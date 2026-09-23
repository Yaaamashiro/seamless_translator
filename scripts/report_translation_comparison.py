"""Render saved measurements without inventing quality scores."""
import json, math, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"artifacts"/"translation-comparison"
def main():
 models={}
 for name in ["hy-mt2","qwen3.5","opus"]:
  path=OUT/(name+".json")
  if path.exists(): models[name]=json.loads(path.read_text(encoding="utf-8-sig"))
 lines=["# 翻訳比較結果", "", "測定日: 2026-09-22。AMD Ryzen 9 5900HS / RAM約16GB / GTX 1650 Max-Q 4GB搭載PC。", "",
 "**今回はCPU実測です。** Windows Smart App Controlがggml-cuda.dllを拒否し、llama.cppはCPUへフォールバックしました。GTX 1650でのGPU速度・必要VRAMは未確認です。", "",
 "日英各12文×2周。ウォームアップ後の翻訳単体、キャッシュ無効、temperature=0。中央値・P95は応答全文が返るまでの時間です。ASR・TTSは含みません。", "",
 "| モデル | 完了リクエスト | 中央値 | P95 | 初期ロード |", "|---|---:|---:|---:|---:|"]
 for name,d in models.items():
  if "median_seconds" in d:
   lines.append(f"| {name} Q4_K_M | {len(d['rows'])} | {d['median_seconds']:.2f}秒 | {d['p95_seconds']:.2f}秒 | {d['load_seconds']:.2f}秒 |")
  else: lines.append(f"| {name} | 実行未完了 | — | — | — |")
 lines+=["", "各方向の中央値:", ""]
 for name,d in models.items():
  for language in ["ja","en"]:
   values=[r["seconds"] for r in d["rows"] if r["source"]==language and r.get("text")]
   if values: lines.append(f"- {name} {'日→英' if language=='ja' else '英→日'}: {statistics.median(values):.2f}秒")
 lines+=["", "## 読み方と制約", "",
 "- 実行成功は訳の正確さを保証しません。自作24文の小規模比較であり、標準ベンチマークの総合順位ではありません。",
 "- OPUS-MTはSciPyのDLLがWindowsのアプリ制御に拒否されました。過去の2例の記録は別条件なので表に混ぜません。",
 "- TranslateGemmaは認証未設定のため、ユーザー指定で保留しています。",
 "- 初期ロードにはライブラリの起動・OSの検査時間も含まれます。純粋な重み読み込み速度ではありません。",
 "- GPUメモリのサンプル値は両モデルともGPU実行を裏付けていません。必要VRAMの推定には使えません。",
 "- 原文に含まれる指示への耐性は各言語1例だけで確認しており、安全性の保証ではありません。",
 "- モデル配布元・固定リビジョン・実行コマンドはdownloads.jsonと各モデルのJSON、起動ログに保存しています。",
 "", "## 全訳文（1周目）", ""]
 for name,d in models.items():
  lines+=["### "+name,"","| ID | 原文 | 訳文 | 秒 |","|---|---|---|---:|"]
  for r in d["rows"]:
   if r["repeat"]!=1: continue
   esc=lambda s:s.replace("|","\\|").replace("\n","<br>")
   lines.append(f"| {r['id']} | {esc(r['input'])} | {esc(r.get('text',r.get('error','')))} | {r['seconds']:.2f} |")
 assessment=OUT/"ASSESSMENT.md"
 if assessment.exists():
  index=lines.index("## 全訳文（1周目）")
  lines[index:index]=[assessment.read_text(encoding="utf-8-sig"), ""]
 (OUT/"RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
if __name__=="__main__": main()
