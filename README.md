# Seamless Translator — Windows 双方向音声翻訳

Windows 11 / Python 3.13で動作する、ターン制自動録音・手動録音に対応した日本語↔英語音声翻訳アプリです。
Mic A → 日本語ASR → 英訳 → 英語TTS → Speaker B、Mic B → 英語ASR → 和訳 → 日本語TTS → Speaker Aを実装しています。

## 初回セットアップ

Windows 11、Python 3.13、uv、CUDA対応NVIDIA GPUが必要です。モデルや実行環境はGitに含みません。検証環境はGTX1650 4GBです。

```powershell
git clone https://github.com/Yaaamashiro/seamless_translator.git
cd seamless_translator
uv sync --locked
```

続いて下記「Gemma / Kokoroの準備」を実行してください。`uv.ps1`はプロジェクト内のuvを優先し、なければPATH上のuvを使用します。`config.yaml`の`translation.gpu_device: Vulkan1`は検証PCの設定です。GPUの列挙順に合わせて変更してください。`gpu_layers: 8`もVRAM容量に応じた設定です。

## 起動

このフォルダーでPowerShellから実行します。

```powershell
.\uv.ps1 run speech-translator
```

1. GUIのMicrophone A / B、Speaker A / Bで実際に使う4機器を選択します。
2. 「設定を保存して準備」を押します。全モデルと機器設定の確認が終わると録音可能になります。
3. 自動会話は「自動翻訳を開始（ターン制）」を押し、一人ずつ話します。発話後の無音で翻訳・再生し、聞き取りへ戻ります。終了は「自動翻訳を停止」です。
4. 手動の場合は `Start A Recording`を押して日本語で話し、同じボタンで停止します。英語音声はSpeaker Bへ出力します。
5. `Start B Recording`を押して英語で話し、停止すると日本語音声をSpeaker Aへ出力します。

キー`1`はA側、`2`はB側の録音開始・停止です（アプリにフォーカスがあるとき）。
録音・処理・再生中は相手側の開始操作と機器変更を無効にします。録音停止は有効のままです。
準備・録音I/O・ASR・翻訳・TTS・再生はワーカースレッドで実行します。
終了時は再生を中止し、実行中の推論が戻ってから録音ストリームを閉じます。

`uv.ps1`はプロジェクト内のuvを呼び出します。uvがPATHにある場合は`uv run speech-translator`でも起動できます。
別のWindows PCでは[uv公式手順](https://docs.astral.sh/uv/getting-started/installation/)でuvを導入し、次を実行します。

```powershell
uv sync --locked
# 下の「Gemma / Kokoroの準備」を実行してから起動
uv run speech-translator
```

初回はモデルのダウンロードが必要です。
音声認識・翻訳・合成はローカルで実行し、会話音声を外部APIへ送信しません。
モデル取得後、ネット接続なしで起動する場合は、起動前に`$env:HF_HUB_OFFLINE = '1'`を設定できます。
Docker・WSL・APIキーは使用しません。

## ターン制の自動翻訳

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

## 単体確認CLI

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

### Gemma / Kokoroの準備

メイン環境の`uv sync --locked`実行後、プロジェクト直下で実行します。

```powershell
.\uv.ps1 run python scripts/prepare_ollama_vulkan.py
Get-ChildItem .tools/ollama-v0.34.2-vulkan -Recurse -File |
  Where-Object { $_.Extension -in '.exe', '.dll' } |
  ForEach-Object {
    $signature = Get-AuthenticodeSignature -LiteralPath $_.FullName
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Ollama') {
      throw "ランタイムの署名検証失敗: $($_.FullName)"
    }
  }
.\uv.ps1 run python scripts/prepare_gemma.py
.\setup_kokoro.ps1
.\uv.ps1 run speech-translator
```

Gemmaは公式Ollama配布物内の署名済みVulkanランタイムを直接起動します。Ollamaサービスの起動は不要です。
Kokoroは`.venv-kokoro`へ分離し、`requirements-kokoro.lock`で依存バージョンを固定しています。
Windows/Python3.13との互換性のため、セットアップ時にmisaki 0.9.4の文字幅変換2箇所をjaconvの同等処理へ置き換えます。
モデルは固定リビジョンから取得し、重みのSHA256を確認します。モデル準備後の推論はローカルです。
準備時に日英の短い音声で初期化するため、最初の会話時に初回GPU初期化待ちが集中しないようにしています。
アプリ終了時は翻訳サーバーとTTSワーカーを解放します。Windowsのセキュリティ設定は変更しません。

Qwenを使用する場合は、`setup_qwen.ps1`で準備し、`--settings config.qwen.yaml`を指定します。
従来構成は`translation.engine: opus`、`tts.engine: legacy`で選べます。

録音はデバイスの標準レート・対応チャンネル数で取得し、mono / float32へ変換します。
ASR入力前にリサンプリングし、Whisperへは16000 Hzで渡します。出力も指定デバイスの標準レートへ変換します。
手動録音は既定で120秒を上限とし、上限超過はエラーにします。長文は翻訳モデルの入力上限で明示的に拒否し、黙って切り捨てません。
無音・空文字・モデル失敗・録音/再生失敗はERRORとして表示し、次の録音で再試行できます。

## 保存されるもの

- `config.local.json`: 実行時の機器選択。
- `models/`: ASR・Gemma・Kokoroなどのモデル。
- `logs/session_*.jsonl`: 方向、機器番号、原文、訳文、発話長、各処理時間、エラー。`application.save_logs: false`で無効化。
- `debug_audio/`: `debug.save_recordings: true`のときのみ通常会話の録音を保存。既定は保存しません。CLIで明示したWAV出力は別です。
- `artifacts/`: 開発時の合成音声・実モデル試験結果・GUI画像。マイク録音ではありません。

`total_latency_sec`は手動の録音停止操作、またはVADによる発話終了確定から出力ストリーム開始までの時間です。自動モードの無音確定待ち時間は含みません。音が耳に届くまでのデバイス遅延は含めません。
ログや録音のパスは設定YAMLのディレクトリを基準に解決します。

## 検証

```powershell
.\uv.ps1 run python -m unittest discover -s tests -v
.\uv.ps1 run python scripts/check_kokoro.py
.\uv.ps1 run python scripts/check_automatic.py
```

自動テスト46件成功。翻訳未完了・不正音声・ワーカータイムアウト・起動失敗時の解放も確認しています。バッファ分離、入出力ルーティング、再サンプリング、無音・エラー復帰、GUI制御と機器保存を確認しています。
現在のGemma / Kokoro構成で、実GPUを使う翻訳→音声生成→生成音声のASR確認を実施しました。

| 方向 | 翻訳結果 | 翻訳 | 音声生成 |
|---|---|---:|---:|
| 日→英 | Where is the station? | 1.06秒 | 0.14秒 |
| 英→日 | 明日の午後3時に2階の受付で会いましょう。 | 4.09秒 | 0.44秒 |

準備は約19.5秒でした。数字の例は発音「にかい」を確認し、ASRでは同音の「2回」と表記されました。
実測値と生成WAVは`artifacts/kokoro-check/`にあります。短文2件の確認であり、全表現の読みや長時間の安定性を保証するものではありません。
切替前のQwenとのGPU比較は`artifacts/tts-comparison/RESULTS.md`に保存しています。比較時のKokoroには今回の日本語読み修正が入っていません。

以下は従来のOPUS / Open JTalk / Piper構成の記録です（Gemma / Qwenの速度ではありません）。TTSで作った例文音声をASR→翻訳→TTSへ渡し、次の結果を得ました。

| 方向 | 認識 | 翻訳 | 処理時間の例 |
|---|---|---|---:|
| A→B | こんにちは。今日は沖縄から来ました。 | Hi. I'm from Okinawa today. | 約3.5秒 |
| B→A | Nice to meet you. | 初めまして | 約2.9秒 |

この時間はファイル出力までの合成音声テストです。物理スピーカーのレイテンシ測定ではありません。
詳細は`artifacts/model-check/results.json`、合成結果は同じフォルダーの`A_translated.wav` / `B_translated.wav`にあります。
実機では入力25・26の取得と出力20・23への小音量テスト音の書き込みが通りましたが、入力はいずれも無音でした。
実モデルをGUIから準備する試験でも録音可能状態に到達しました。準備は約21秒で、その間もGUIイベントを処理しました。
初回のライブラリ初期化には最大約2.5秒のPythonイベント間隔が見られたため、準備開始直後に操作が遅れる場合があります。
**2人の実発話・4機器での聞き取り・交互会話の受入確認は未完了です。** 使用機器を選択し、上の録音/再生CLIから順に確認してください。
自動モードは実Silero VAD・ASR・Gemma・Kokoroを使い、日英各1ターンを確認しました。再生音声を両マイクの模擬コールバックへ戻しても追加の翻訳が起きないことを確認しています。記録は`artifacts/automatic-check/results.json`です。物理的なマイク・スピーカーの残響試験は未実施です。AEC、逐次翻訳、同時発話は未対応です。

## 構造

`audio/`、`asr/`、`translation/`、`tts/`を独立させ、`pipeline/channel.py`に依存注入します。
ASR/Translator/TTSのProtocolを満たす別実装を`pipeline/engines.py`から渡せます。
各Channelが専用ワーカーを持ち、MVPの交互会話制限は`Coordinator`とGUIに置いています。
`gui/`とCLIは同じ音声I/O・Channelを使用します。

開発用スクリプトの用途と実行順は[開発ガイド](docs/DEVELOPMENT.md)を参照してください。`artifacts/`の測定記録・WAV・GUI画像はローカル生成物のため、このリポジトリには含めていません。

## エンジン・モデル参照

- [Kokoro公式実装](https://github.com/hexgrad/kokoro) / [Kokoro-82Mモデル](https://huggingface.co/hexgrad/Kokoro-82M)

- [Gemma 4 E4B公式GGUF](https://huggingface.co/google/gemma-4-E4B-it-qat-q4_0-gguf)
- [Qwen3-TTS公式実装](https://github.com/QwenLM/Qwen3-TTS) / [0.6B CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice)
- [Ollamaランタイム](https://github.com/ollama/ollama/releases/tag/v0.34.2)

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) / [Whisper](https://github.com/openai/whisper)
- [OPUS 日英モデル](https://huggingface.co/Helsinki-NLP/opus-mt-ja-en) / [OPUS Tatoeba 英日モデル](https://huggingface.co/Helsinki-NLP/opus-tatoeba-en-ja)
- [pyopenjtalk-plus](https://github.com/tsukumijima/pyopenjtalk-plus)
- [Piper](https://github.com/OHF-Voice/piper1-gpl) / [Lessac音声のモデルカード](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/lessac/medium/MODEL_CARD)
- [sounddevice](https://python-sounddevice.readthedocs.io/en/latest/) / [PySide6](https://doc.qt.io/qtforpython-6/)

Mei音声: MMDAgent Project Team / Nagoya Institute of Technology, Department of Computer Science (2009–2013)、CC BY 3.0。
各エンジンとモデルのライセンスは個別です。Meiのライセンス文は`THIRD_PARTY/Mei-voice-license.txt`に同梱しています。
