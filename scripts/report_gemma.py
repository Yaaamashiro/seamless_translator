"""Generate the final GPU-only comparison report and validate recorded evidence."""
import json,re,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"artifacts"/"gemma-comparison"
NAMES=["gemma4-e2b","gemma4-e4b","hy-mt2","qwen3.5"]
def main():
 data={name:json.loads((OUT/(name+"-vulkan.json")).read_text(encoding="utf-8-sig")) for name in NAMES}
 for name,d in data.items():
  assert len(d["rows"])==48 and d["request_failures"]==0, name
  assert d["backend_observed"].startswith("vulkan") and d["gpu_peak_board_mib"]>0,name
  assert all(r["finish_reason"]=="stop" and r["text"] for r in d["rows"]),name
  assert all(r["usage"]["prompt_tokens_details"]["cached_tokens"]==0 for r in d["rows"]),name
  assert any("offloaded" in line and "layers to GPU" in line for line in d["allocation_log"]),name
 lines=["# GTX 1650での翻訳GPU比較","",
 "測定日: 2026-09-22。GTX 1650 Max-Q 4GB / Ryzen 9 5900HS / RAM約16GB / NVIDIAドライバー555.97。",
 "",
 "**E2B・E4BともGTX 1650で実行できました。** GPU用ランタイムの問題は、署名が有効なOllama公式配布内のllama.cpp + Vulkanへ切り替えて解決しました。Smart App Controlは有効のままで、ドライバー・セキュリティ設定・システムPATHは変更していません。",
 "",
 "## 実測",
 "",
 "| モデル | 重みファイル（GB） | GPUボード使用量の最大値（MiB / GiB） | 翻訳中央値 | P95 | 完了件数 |",
 "|---|---:|---:|---:|---:|---:|"]
 for name,d in data.items():
  size=Path(d["artifact"]["file"]).stat().st_size/1e9
  mib=d["gpu_peak_board_mib"]
  lines.append(f"| {name} | {size:.2f} | {mib} / {mib/1024:.2f} | {d['median_seconds']:.2f}秒 | {d['p95_seconds']:.2f}秒 | 48/48 |")
 lines+=["",
 "ファイル容量は10進GB、メモリはMiB/GiBです。GPU値はnvidia-smiで約0.5秒以上の間隔で測ったボード全体の最大値で、他プロセスの使用も含みます。モデル単体の厳密な割り当て量ではありません。", "",
 "## ファイル容量とGPU配置の違い","",
 "E4Bのファイルは約5.15GBですが、GPU側のモデルバッファは約2696MiBでした。CPU側にも約2730MiBのモデルマッピングが残ります。計算レイヤーのGPU配置と、重み全体がVRAMだけに存在することは別です。このRAM併用の配置でVRAMの実測最大値は2952MiBでした。",
 "",
 "E2BもGPU側のモデルバッファ約1342MiB、CPU側のモデルマッピング約2153MiBという構成です。ファイルサイズ・マッピング容量・物理メモリ常駐量を同一視していません。", "",
 "### 配置ログ抜粋",""]
 for name,d in data.items():
  lines+=["**"+name+"**","","```text"]
  lines += [line for line in d["allocation_log"] if any(word in line for word in ["using device","offloaded","model buffer size","KV buffer size","compute buffer size"])]
  lines+=["```",""]
 lines+=["## 訳文の評価","",
 "**この24文では、品質を優先する候補はGemma 4 E4B、速度とメモリの余裕を優先する候補はE2Bです。** 小規模な自作例の目視評価であり、一般的な性能順位ではありません。", "",
 "| 確認項目 | E2B | E4B |",
 "|---|---|---|",
 "| 乳製品は食べられない（ja05） | 食品一般が食用かどうかという表現に寄る | I can eat eggs, but I cannot eat dairy products. と個人の事情を保持 |",
 "| 否定・条件（ja04、en04、en12） | 今回は意味を保持 | 今回は意味を保持 |",
 "| 原文内の『翻訳せず返答せよ』（ja11、en11） | Understood / OKだけを返し、翻訳を中断 | 指示文そのものを翻訳 |",
 "| locked myself out（en10） | 『鍵をかけ忘れた』と誤訳 | 『鍵をかけちゃって、鍵がまだ中』と状況をより保持。ただし締め出されたことを明示していない |",
 "",
 "Hy-MT2は軽量で速く、原文内の指示文も翻訳しましたが、条件文の英語の文法や締め出された状況に誤りがありました。Qwen3.5 2Bは今回の英→日でnearest→最近、unlessの条件逆転、原文内の指示への追従などが残りました。", "",
 "## 条件・制限","",
 "- Google公式Gemma QAT Q4_0と、前回取得済みのHy-MT2/Qwen Q4_K_M。モデルの量子化方式は異なります。",
 "- 実行環境は4モデルともOllama v0.34.2配布内の署名済みllama.cpp（起動ログ: build 1 / commit 391fac164）、Vulkan1 = GTX 1650を明示指定。",
 "- 日→英12文、英→日12文を2周。各方向1文のウォームアップ後、全文の応答が返るまでを測定。",
 "- コンテキスト2048、並列1、temperature=0、seed=42、出力上限256。思考モード無効。",
 "- リクエストのprompt cacheに加え、サーバーのcache-ramとcontext checkpointsも無効。全192件でcached_tokens=0を確認。",
 "- GPU配置はauto、fit-target=256MiB。重みの配置はランタイムの判断に従い、ログに保存。",
 "- 初回E2Bではサーバー側キャッシュ等が有効な状態で48件目が接続切断。その記録をinitialファイルに保存。サーバー側キャッシュ等を無効化した再測定では48/48完了したが、切断原因を断定したものではない。",
 "- 音声認識・TTS・画像/音声エンコーダーは未ロード。実会話の全体遅延、Qwen TTS等とのGPU同時常駐、長時間連続運転は未検証。",
 "- リクエスト成功は訳の正しさの保証ではない。原文内の指示文の例も各方向1文であり、広い耐性の保証ではない。",
 "- 本番アプリの翻訳器の切り替えは、この比較作業には含めていません。既定設定は従来のまま。",
 "",
 "## 全訳文（1周目）",""]
 for name,d in data.items():
  lines+=["### "+name,"","| ID | 原文 | 訳文 | 秒 |","|---|---|---|---:|"]
  for r in d["rows"]:
   if r["repeat"]!=1:continue
   clean=lambda s:s.replace("|","\\|").replace("\n","<br>")
   lines.append(f"| {r['id']} | {clean(r['input'])} | {clean(r['text'])} | {r['seconds']:.2f} |")
 lines+=["","再現手順: [README](README.md)。各モデルのJSONに全リクエスト、メモリサンプル、コマンド、配布元と固定リビジョンを記録。"]
 (OUT/"RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
 print("Validated 192 GPU requests: complete outputs, zero cached tokens, GPU offload confirmed.")
if __name__=="__main__":main()
