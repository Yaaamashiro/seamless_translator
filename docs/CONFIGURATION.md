# 設定・CLIリファレンス

[READMEへ戻る](../README.md)

## 自動翻訳

マイクAは日本語、マイクBは英語として固定します。先に発話を検知したマイクがそのターンを取得します。人物識別や入力言語の自動判定は行いません。相手の声を両方のマイクが拾う場合は誤った側が選ばれるため、マイクの配置・距離・入力レベルを調整してください。

faster-whisperに同梱されたSilero VADをCPUで動かして発話を検出します。単なる音量閾値ではありません。約0.7秒の無音で発話を確定し、認識→翻訳→合成→再生を行います。翻訳・再生中と再生終了後0.6秒間は両マイクの入力を破棄し、その後に新しい発話を受け付けます。この間に話した内容は次のターンへ持ち越しません。画面の「聞き取り中」を待って話してください。

これは再生タイミングを使ったループ防止です。音声波形を照合・除去するAECは未実装で、長い残響を保証して除去するものではありません。同時発話には対応しません。自動モード開始から停止まで両方の入力ストリームを開き、停止時に閉じます。

`config.yaml`の`automatic`で調整できます。

| 設定 | 既定値 | 意味 |
|---|---:|---|
| threshold | 0.6 | VADの発話確率閾値 |
| start_ms | 96 | 発話開始に必要な連続検出時間 |
| min_speech_ms | 256 | 翻訳対象とする最小発話時間 |
| silence_ms | 704 | 発話終了とする無音時間 |
| pre_roll_ms | 320 | 語頭を残すための先行バッファ |
| playback_guard_ms | 600 | 再生終了後の入力除外時間 |
| max_utterance_seconds | 20 | 発話上限。超過した発話全体を破棄し、無音を待って再開 |

自動モード中は手動録音と機器変更を無効にします。停止後は手動録音へ戻れます。

## 機器設定とルーティング

選択は`config.local.json`に番号・名前・ホストAPIを保存します。次回起動時は名前とホストAPIが一意に一致した機器を復元します。
再接続で番号が変わった場合も名前で照合し、見つからない場合・同名機器が複数ある場合は再選択が必要です。
GUI起動時の選択値を引数で指定することもできます。番号は例なので、現在の一覧で確認してください。

```powershell
.\uv.ps1 run speech-translator --list-devices
.\uv.ps1 run speech-translator --mic-a 25 --mic-b 26 --speaker-a 23 --speaker-b 20
.\uv.ps1 run speech-translator --configure
```

`--configure`はCLIの対話選択です。保存値をEnterで再利用でき、省略した役割だけ対話入力します。
`--config <path>`で機器設定の保存先、`--settings <path>`でモデル設定YAMLを変更できます。
同じ機器がMME、DirectSound、WASAPI、WDM-KSに重複表示されることがあります。WASAPIを一覧の先頭に表示しています。
同一番号のA/B割り当ては拒否しますが、別APIが同じ物理機器を指すかは自動判定できません。
Windowsの既定機器を指すSound Mapperや仮想入力を、別の物理機器として数えないでください。
USBを抜き差しして再取得でも反映されない場合はアプリを再起動してください。

## CLIでの動作確認

以下の番号は例です。`--list-devices`で確認して置き換えてください。
録音テストはEnterで開始、もう一度Enterで停止します。テストで指定したWAVは保存されます。

```powershell
# Step 1–2: 環境・列挙
.\uv.ps1 run python --version
.\uv.ps1 run python -m speech_translator.main --list-devices --json

# Step 3: A/Bの録音を個別確認
.\uv.ps1 run speech-translator --test-record --input 25 --output-wav debug_audio/A.wav
.\uv.ps1 run speech-translator --test-record --input 26 --output-wav debug_audio/B.wav

# Step 4: 指定スピーカーへの再生
.\uv.ps1 run speech-translator --test-play debug_audio/A.wav --output 20
.\uv.ps1 run speech-translator --test-play debug_audio/B.wav --output 23

# Step 5: 機器選択→録音→相手側への原音再生
.\uv.ps1 run speech-translator --cross-route A
.\uv.ps1 run speech-translator --cross-route B

# Step 6: WAVからASR
.\uv.ps1 run speech-translator --asr debug_audio/A.wav --language ja
.\uv.ps1 run speech-translator --asr debug_audio/B.wav --language en

# Step 7: テキスト翻訳
.\uv.ps1 run speech-translator --translate 'こんにちは。今日は沖縄から来ました。' --source-language ja
.\uv.ps1 run speech-translator --translate 'Nice to meet you.' --source-language en

# Step 8: 音声合成
.\uv.ps1 run speech-translator --tts 'Hello.' --language en --output-wav debug_audio/en.wav
.\uv.ps1 run speech-translator --tts 'はじめまして。' --language ja --output-wav debug_audio/ja.wav

# Step 9: WAVから翻訳音声を指定機器へ再生
.\uv.ps1 run speech-translator --pipeline debug_audio/A.wav --direction A --output 20
.\uv.ps1 run speech-translator --pipeline debug_audio/B.wav --direction B --output 23

# CLIで交互会話 / 全モデルの準備確認 / GUI
.\uv.ps1 run speech-translator --cli
.\uv.ps1 run speech-translator --check-models
.\uv.ps1 run speech-translator --gui
```

## モデル・音声設定

`config.yaml`を編集してアプリを再起動します。GUIとCLIは同じ設定を使います。

| モジュール | 既定実装 |
|---|---|
| ASR | faster-whisper small、CPU / int8 |
| 日英翻訳 | Gemma 4 E4B IT / 公式QAT Q4_0 GGUF、Vulkan GPU＋CPU |
| 日英TTS | Kokoro 82M v1.0、CUDA / FP32 |
| 日本語の声 | jf_alpha |
| 英語の声 | af_heart |
| Audio I/O / GUI | sounddevice / PortAudio、PySide6 |

`translation.engine: gemma4`、`tts.engine: kokoro`が既定です。
GemmaのGPU配置は8/43層、GPUは`Vulkan1`（このPCのGTX1650）です。Kokoroの合成演算は`cuda:0`を使用し、CPUへの自動切替は行いません。
日本語はOpen JTalkで数字・助数詞を文脈に応じた読みにしてからKokoroへ渡します。特定の単語や「2階」だけを個別置換する処理は入れていません。全ての固有名詞や数値表現の読みを保証するものではありません。
音声生成時に510文字を超える発音列は明示的に拒否します。長い発話は区切って話してください。
`tts.ja_speaker` / `tts.en_speaker`で声を指定できますが、対応する音声ファイルを`models/kokoro-82m/voices/`へ用意する必要があります。

## 保存されるもの

- `config.local.json`: 実行時の機器選択。
- `models/`: ASR・Gemma・Kokoroなどのモデル。
- `logs/session_*.jsonl`: 方向、機器番号、原文、訳文、発話長、各処理時間、エラー。`application.save_logs: false`で無効化。
- `debug_audio/`: `debug.save_recordings: true`のときのみ通常会話の録音を保存。既定は保存しません。CLIで明示したWAV出力は別です。
- `artifacts/`: 開発時の合成音声・実モデル試験結果・GUI画像。マイク録音ではありません。

`total_latency_sec`は手動の録音停止操作、またはVADによる発話終了確定から出力ストリーム開始までの時間です。自動モードの無音確定待ち時間は含みません。音が耳に届くまでのデバイス遅延は含めません。
ログや録音のパスは設定YAMLのディレクトリを基準に解決します。
