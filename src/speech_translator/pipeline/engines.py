import logging
from speech_translator.config import setup_model_cache

def create_translator(config, progress=print):
    setup_model_cache(config)
    if config['translation']['engine'] == 'gemma4':
        from speech_translator.translation.gemma import GemmaTranslator
        return GemmaTranslator(config['translation'], progress)
    from speech_translator.translation.opus_mt import OpusTranslator
    return OpusTranslator(config['translation'], progress)

def create_tts(config, progress=print):
    root = setup_model_cache(config)
    if config['tts']['engine'] == 'kokoro':
        from speech_translator.tts.kokoro import KokoroTTS
        return KokoroTTS(config['tts'], progress)
    if config['tts']['engine'] == 'qwen3':
        from speech_translator.tts.qwen import QwenTTS
        return QwenTTS(config['tts'], progress)
    from speech_translator.tts.engine import LocalTTS
    return LocalTTS(config['tts'], root / 'piper', progress)

def close_engines(engines):
    for engine in reversed(engines or ()):
        close = getattr(engine, 'close', None)
        if close:
            try:
                close()
            except Exception:
                logging.getLogger(__name__).exception('モデル終了処理に失敗しました')

def load_engines(config, progress=print):
    root = setup_model_cache(config)
    engines = []
    try:
        progress('ASR: ロード中')
        from speech_translator.asr.faster_whisper import FasterWhisperASR
        engines.append(FasterWhisperASR(config['asr'], root / 'whisper'))
        progress('✓ ASR')
        engines.append(create_translator(config, progress))
        engines.append(create_tts(config, progress))
        return tuple(engines)
    except BaseException:
        close_engines(engines)
        raise
