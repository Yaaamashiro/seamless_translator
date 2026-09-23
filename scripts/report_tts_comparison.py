"""Create a comparison report from measured GPU and ASR results."""
import html,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/tts-comparison'
data={name:json.loads((OUT/(name+'-reviewed.json')).read_text(encoding='utf-8')) for name in ['qwen','kokoro']}
summary={}
for name,d in data.items():
 rows=[r for r in d['rows'] if r['repeat']>=0 and 'error' not in r]
 gpu=json.loads((OUT/(name+'-gpu.json')).read_text())
 summary[name]={'successful_requests':len(rows),'failed_requests':sum('error' in r for r in d['rows']),'load_seconds':d['load_seconds'],'median_seconds':statistics.median(r['seconds'] for r in rows),'min_seconds':min(r['seconds'] for r in rows),'max_seconds':max(r['seconds'] for r in rows),'median_rtf':statistics.median(r['rtf'] for r in rows),'peak_board_mib':gpu['peak_board_mib'],'allocated_peak_mib':max(r['allocated_peak_mib'] for r in rows),'reserved_peak_mib':max(r['reserved_peak_mib'] for r in rows)}
summary['median_speed_ratio']=summary['qwen']['median_seconds']/summary['kokoro']['median_seconds']
(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
lines=['# GTX1650: Qwen / Kokoro TTS比較','', '本番設定はGemma 4 E4B + Qwenのままです。config.yaml・src・既存ロックファイルのSHA256照合結果はproduction-verification.jsonに保存しています。','', '## 条件','', '- GTX1650 Max-Q 4GB、PyTorch 2.7.1 + CUDA 12.6、CPUスレッド数2。両モデルとも音声合成はGPU。','- Gemma E4B QAT Q4_0を本番と同じ8/43層GPU配置で常駐。TTSは1種類ずつ順に測定。','- 日英4文ずつ（計8文）を各2回、各モデル16件。各言語のウォームアップを先に1件実行。seed 42 / 43。','- 生成時間は文字から音声全体が完成するまで。前処理とGPU同期を含む。モデル起動、WAV保存、再認識、再生は含まない。','- Qwen: 0.6B CustomVoice、ono_anna / ryan、本体FP16・予測部とコーデックFP32。既存アプリと同じ推論構成。','- Kokoro: 82M v1.0、jf_alpha / af_heart、FP32、speed=1。声が異なるため音声長は一致しない。','- Kokoroの比較専用環境ではmisakiのmojimoji文字幅変換2箇所をjaconvに置換（Windows/Python3.13互換性）。pyopenjtalk-plus / unidic-lite利用。元ファイルと変更ファイルも保存。','', '## 実測結果','', '| 指標 | Qwen | Kokoro |','|---|---:|---:|']
for title,key,fmt in [('生成時間中央値（秒）','median_seconds','.3f'),('最短（秒）','min_seconds','.3f'),('最長（秒）','max_seconds','.3f'),('RTF中央値','median_rtf','.3f'),('GPU全体最大（MiB、Gemma含む）','peak_board_mib','.0f'),('TTS CUDA割当最大（MiB）','allocated_peak_mib','.0f'),('TTS CUDA予約最大（MiB）','reserved_peak_mib','.0f'),('モデル・前処理初期化（秒）','load_seconds','.2f')]:
 lines.append('| '+title+' | '+format(summary['qwen'][key],fmt)+' | '+format(summary['kokoro'][key],fmt)+' |')
lines += ['',f"今回の生成時間中央値の比は約{summary['median_speed_ratio']:.1f}倍。RTFは生成秒数÷音声秒数で、1未満なら再生時間より速く生成できる。GPU全体最大はnvidia-smiによる約0.5秒間隔の観測で瞬間ピークを取り逃す可能性がある。",'', '## 文ごとの生成時間（2回の平均、秒）','', '| 入力 | Qwen | Kokoro |','|---|---:|---:|']
cases=json.loads((OUT/'cases.json').read_text(encoding='utf-8-sig'))
for c in cases:
 vals=[statistics.mean(r['seconds'] for r in data[n]['rows'] if r['id']==c['id'] and r['repeat']>=0 and 'error' not in r) for n in ['qwen','kokoro']]
 lines.append(f"| {c['text']} | {vals[0]:.2f} | {vals[1]:.2f} |")
lines += ['', '## 読み上げ確認（1回目）','', 'ASRによる再認識は補助指標で、自然さの採点ではありません。認識器の誤りもあり得るため、保存音声を併せて確認してください。','', '| 入力 | Qwenの再認識 | Kokoroの再認識 |','|---|---|---|']
for c in cases:
 rs=[next(r for r in data[n]['rows'] if r['id']==c['id'] and r['repeat']==0) for n in ['qwen','kokoro']]
 lines.append('| '+c['text']+' | '+' | '.join(r.get('asr',r.get('error','')) for r in rs)+' |')
lines += ['', '## 制約','', '- 8文・各2回の局所的な比較。長時間運用・幅広い固有名詞・複数話者の品質は未評価。','- Kokoro日本語の「2階」は発音列が「に きざはし」相当になっている。数字・助数詞の読みの追加検証が必要。','- 設定変更やKokoroのアプリ組み込みは行っていない。','']
(OUT/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
parts=['<!doctype html><meta charset="utf-8"><title>TTS音声比較</title><style>body{font-family:system-ui;max-width:1100px;margin:32px auto;padding:16px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:12px}audio{width:290px}small{color:#555}</style><h1>Qwen / Kokoro：同じ文章の音声比較</h1><p>本番設定は変更していません。GTX1650上で生成。声の自然さと日本語の数字の読みを聞き比べてください。</p><table><tr><th>文章</th><th>Qwen</th><th>Kokoro</th></tr>']
for c in cases:
 parts.append('<tr><td>'+html.escape(c['text'])+'</td>')
 for n in ['qwen','kokoro']:
  r=next(r for r in data[n]['rows'] if r['id']==c['id'] and r['repeat']==0)
  parts.append(f'<td><audio controls preload="none" src="{html.escape(r["wav"])}"></audio><br><small>生成 {r["seconds"]:.2f}秒 / 音声 {r["audio_seconds"]:.2f}秒</small></td>')
 parts.append('</tr>')
parts.append('</table><p>詳細：RESULTS.md / summary.json。ASR結果は自然さの採点ではありません。</p>')
(OUT/'listen.html').write_text('\n'.join(parts),encoding='utf-8')
print(json.dumps(summary,indent=2),flush=True)
