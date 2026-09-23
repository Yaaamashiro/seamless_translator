# 開発ガイド

すべてプロジェクト直下から実行します。

## 構成

| パス | 用途 |
|---|---|
| `src/speech_translator/` | GUI、CLI、録音・再生、VAD、認識、翻訳、音声合成 |
| `tests/` | モデルのダウンロードや物理デバイスを必要としない単体テスト |
| `scripts/` | モデル準備、実モデルの検証、性能比較 |
| `config.yaml` | Gemma + Kokoroの既定設定 |
| `config.qwen.yaml` | Qwen TTSを使う代替設定 |
| `requirements-*.lock` | 分離したTTS環境の依存関係 |
| `THIRD_PARTY/` | 同梱する第三者のライセンス表示 |

## 通常の検証

```powershell
.\uv.ps1 sync --locked
.\uv.ps1 run python -m unittest discover -s tests -v
.\uv.ps1 run python scripts/preview_gui.py
```

GUIテストはoffscreenで実行します。プレビューは`artifacts/gui.png`へ出力します。

## 実GPU・実モデルの検証

[モデルのセットアップ](SETUP.md)を済ませてから実行します。CPUのみのCIでは実行しません。

```powershell
.\uv.ps1 run python scripts/check_kokoro.py
.\uv.ps1 run python scripts/check_automatic.py
```

`check_automatic.py`は先行する`check_kokoro.py`が生成した日英WAVを入力に使います。実VAD・ASR・翻訳・TTSを使いますが、入力は模擬マイク、出力はファイルです。物理的な回り込み・残響・マイク配置は別途実機で確認してください。

`check_audio.py`、`check_gui_models.py`、`check_models.py`、`check_gemma_qwen.py`は個別の機器・旧構成・モデル検証用です。実行前にスクリプト内の設定を確認してください。

## モデル選定時の比較スクリプト

`compare_*`、`report_*`、`review_tts_comparison.py`、`tts_comparison_worker.py`、`run_gpu_comparison.ps1`と比較用`prepare_*_comparison.py`はモデル選定時の実験用です。実験によって追加モデルや`artifacts/`内の先行結果が必要になります。通常起動には必要ありません。

通常のモデル準備には[セットアップ手順](SETUP.md)にある`prepare_ollama_vulkan.py`、`prepare_gemma.py`、`setup_kokoro.ps1`を使います。`prepare_gemma.py`は比較スクリプト内のダウンロード関数を共用します。

## 公開対象

モデル・仮想環境・実行バイナリ・会話ログ・録音・機器の保存設定・測定生成物はGitから除外します。除外ファイルはローカルに保持します。新しい依存関係を追加した場合は対応するロックファイルも更新してください。

第三者モデル・エンジンの利用条件はそれぞれの配布元で確認してください。リポジトリ全体への新たなOSSライセンスは設定していません。
