# モデルのセットアップ

[READMEへ戻る](../README.md)

WindowsのPowerShellで、リポジトリ直下から実行してください。事前に`uv sync --locked`でメイン環境を作成します。初回はインターネット接続が必要です。

## Gemma / Kokoro

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

## GPUの設定

`config.yaml`の`translation.gpu_device: Vulkan1`は検証PCのGTX1650を指します。GPUの列挙順は環境により異なるため、使用するGPUに合わせて変更してください。`translation.gpu_layers: 8`も検証環境向けの値です。Kokoroは`tts.device: cuda:0`を使用します。

## オフライン起動

モデルの取得と初回準備を済ませた後は、次のように起動できます。

```powershell
$env:HF_HUB_OFFLINE = '1'
.\uv.ps1 run speech-translator
```
