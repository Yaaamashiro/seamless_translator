"""Desktop application and independently runnable diagnostics."""
import argparse
import json
import sys
from pathlib import Path
from speech_translator.audio.devices import format_devices, list_devices
from speech_translator.audio.selection import ROLES, choose_devices, load_selection, save_selection


def parser_for_cli():
    parser = argparse.ArgumentParser(description='Windows 双方向音声翻訳デモ（引数なしでGUI起動）')
    modes = parser.add_mutually_exclusive_group()
    for flag, help_text in [('gui', 'GUIを起動（既定）'), ('list-devices', 'デバイス列挙'),
                            ('configure', 'CLIで4機器を選択・保存'), ('cli', 'CLIで双方向翻訳'),
                            ('test-record', '手動録音してWAV保存'), ('check-models', '全モデルを取得・ロード確認')]:
        modes.add_argument('--' + flag, action='store_true', help=help_text)
    for flag, help_text in [('test-play', '指定スピーカーでWAV再生'), ('asr', 'WAVを音声認識'),
                            ('pipeline', 'WAV→ASR→翻訳→TTS→指定出力')]:
        modes.add_argument('--' + flag, type=Path, metavar='WAV', help=help_text)
    modes.add_argument('--cross-route', choices=['A', 'B'], help='A→B/B→Aの録音・原音再生')
    modes.add_argument('--translate', metavar='TEXT', help='テキストを翻訳')
    modes.add_argument('--tts', metavar='TEXT', help='テキストを音声化してWAV保存')
    parser.add_argument('--json', action='store_true', help='デバイス一覧をJSON形式で出力')
    parser.add_argument('--config', type=Path, default=Path('config.local.json'), help='デバイス選択の保存先')
    parser.add_argument('--settings', type=Path, default=Path('config.yaml'), help='モデル・アプリ設定YAML')
    parser.add_argument('--input', type=int, help='単体録音テストの入力番号')
    parser.add_argument('--output', type=int, help='単体再生/ファイルパイプラインの出力番号')
    parser.add_argument('--output-wav', type=Path, help='録音テスト/TTSの保存先')
    parser.add_argument('--language', choices=['ja', 'en'], default='ja', help='ASR入力/TTS出力の言語')
    parser.add_argument('--source-language', choices=['ja', 'en'], default='ja', help='翻訳元言語')
    parser.add_argument('--direction', choices=['A', 'B'], default='A', help='ファイルパイプラインの方向')
    for role in ROLES:
        parser.add_argument('--' + role.replace('_', '-'), type=int, help=f'{role} のデバイス番号')
    return parser


def select(args, devices):
    print(format_devices(devices))
    try:
        saved = load_selection(args.config)
    except (ValueError, OSError) as exc:
        print(f'前回の設定を読み込めません。再選択してください: {exc}', file=sys.stderr)
        saved = {}
    selected = choose_devices(devices, saved, {role: getattr(args, role) for role in ROLES})
    save_selection(args.config, selected)
    for source, target in [('mic_a', 'speaker_b'), ('mic_b', 'speaker_a')]:
        print(f'{source}: {selected[source].name} ({selected[source].index})'
              f' → {target}: {selected[target].name} ({selected[target].index})')
    print(f'設定を保存しました: {args.config.resolve()}')
    return selected


def record(device, config):
    from speech_translator.audio.recorder import Recorder
    recorder = Recorder(device, config['audio']['max_recording_seconds'])
    try:
        input('Enterで録音開始: ')
        recorder.start()
        input('録音中です。Enterで停止: ')
        return recorder.stop()
    finally:
        recorder.close()


def ensure_device(number, kind):
    attribute = 'input_channels' if kind == 'input' else 'output_channels'
    if number is None or not any(d.index == number and getattr(d, attribute) > 0 for d in list_devices()):
        raise ValueError(f'--{kind} に一覧の有効な{kind}デバイス番号を指定してください。')


def run(args):
    if args.list_devices:
        devices = list_devices()
        print(json.dumps([d.to_dict() for d in devices], ensure_ascii=False, indent=2)
              if args.json else format_devices(devices))
        if not any(d.input_channels for d in devices) or not any(d.output_channels for d in devices):
            raise ValueError('入力または出力デバイスがありません。Windowsのサウンド設定を確認してください。')
        return 0
    from speech_translator.config import load_config, setup_model_cache
    config = load_config(args.settings)
    import logging
    logging.basicConfig(level=logging.DEBUG if config['debug']['verbose'] else logging.WARNING)
    if args.configure:
        select(args, list_devices())
        return 0
    modes = (args.cli, args.test_record, args.test_play, args.cross_route, args.asr,
             args.translate is not None, args.tts is not None, args.pipeline, args.check_models)
    if not any(modes):
        from speech_translator.gui.main_window import run_gui
        return run_gui(config, args.config, {role: getattr(args, role) for role in ROLES})
    from speech_translator.audio.pcm import Audio
    from speech_translator.audio.player import Player
    if args.test_record:
        ensure_device(args.input, 'input')
        if not args.output_wav:
            raise ValueError('--output-wav で保存先を指定してください。')
        audio = record(args.input, config)
        audio.save(args.output_wav)
        print(f'{audio.duration:.2f} sec → {args.output_wav}')
        return 0
    if args.test_play:
        ensure_device(args.output, 'output')
        Player(args.output).play(Audio.load(args.test_play))
        return 0
    if args.cross_route:
        selected = select(args, list_devices())
        side = args.cross_route.lower()
        destination = 'b' if side == 'a' else 'a'
        audio = record(selected[f'mic_{side}'].index, config)
        Player(selected[f'speaker_{destination}'].index).play(audio)
        return 0
    root = setup_model_cache(config)
    if args.asr:
        from speech_translator.asr.faster_whisper import FasterWhisperASR
        audio = Audio.load(args.asr)
        engine = FasterWhisperASR(config['asr'], root / 'whisper')
        print(engine.transcribe(audio.samples, audio.sample_rate, args.language))
        return 0
    if args.translate is not None:
        from speech_translator.pipeline.engines import create_translator, close_engines
        engine = create_translator(config, print)
        try:
            print(engine.translate(args.translate, args.source_language, 'en' if args.source_language == 'ja' else 'ja'))
        finally:
            close_engines((engine,))
        return 0
    if args.tts is not None:
        if not args.output_wav:
            raise ValueError('--output-wav で保存先を指定してください。')
        from speech_translator.pipeline.engines import create_tts, close_engines
        engine = create_tts(config, print)
        try:
            engine.synthesize(args.tts, args.language).save(args.output_wav)
        finally:
            close_engines((engine,))
        print(args.output_wav)
        return 0
    from speech_translator.pipeline.engines import load_engines, close_engines
    from speech_translator.logging.session_logger import SessionLogger
    from speech_translator.pipeline.channel import Channel
    from speech_translator.pipeline.coordinator import build_channels
    if args.pipeline:
        ensure_device(args.output, 'output')
    selected = select(args, list_devices()) if args.cli else None
    engines = load_engines(config)
    try:
        if args.check_models:
            print('✓ 全モデルの準備完了')
            return 0
        logger = SessionLogger(config['application']['log_directory'], config['application']['save_logs'])
        def notify(event):
            for key in ('state', 'asr_text', 'translated_text', 'error', 'total_latency_sec'):
                if key in event and event[key] is not None:
                    print(f'[{event["direction"]}] {key}: {event[key]}')
        if args.pipeline:
            source, target = ('ja', 'en') if args.direction == 'A' else ('en', 'ja')
            channel = Channel('A_TO_B' if args.direction == 'A' else 'B_TO_A', -1, args.output,
                              source, target, *engines, config, logger, notify)
            try:
                return 0 if channel.process(Audio.load(args.pipeline)) is not None else 1
            finally:
                channel.close().result()
        channels = build_channels(selected, engines, config, logger, notify)
        try:
            while True:
                choice = input('A / B で方向選択、Q で終了: ').strip().upper()
                if choice == 'Q':
                    break
                if choice not in ('A', 'B'):
                    continue
                channel = channels['A_TO_B' if choice == 'A' else 'B_TO_A']
                try:
                    channel.process(record(channel.input_device, config))
                except Exception as exc:
                    print(f'録音失敗: {exc}', file=sys.stderr)
        finally:
            for channel in channels.values():
                channel.close().result()
        return 0
    finally:
        close_engines(engines)


def main(argv: list[str] | None = None) -> int:
    parser = parser_for_cli()
    args = parser.parse_args(argv)
    if args.json and not args.list_devices:
        parser.error('--json は --list-devices と一緒に指定してください。')
    try:
        return run(args)
    except (EOFError, KeyboardInterrupt):
        print('\n操作を中止しました。', file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
