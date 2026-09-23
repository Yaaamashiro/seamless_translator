"""Isolated official Qwen TTS worker. Stdout is reserved for JSON RPC."""
import base64
import contextlib
import json
import sys
import traceback
from qwen_runtime import stabilize_fp16, bounded_generate

def send(value):
    sys.stdout.write(json.dumps(value, ensure_ascii=False) + '\n')
    sys.stdout.flush()

def main():
    config = json.loads(sys.argv[1])
    try:
        with contextlib.redirect_stdout(sys.stderr):
            import numpy as np
            import torch
            torch.set_num_threads(2)
            from qwen_tts import Qwen3TTSModel
            if config['device'].startswith('cuda') and not torch.cuda.is_available():
                raise RuntimeError('Qwen TTS用CUDAが利用できません。CPUへ自動切替しません。')
            model = Qwen3TTSModel.from_pretrained(
                config['model_path'], device_map=config['device'],
                dtype=getattr(torch, config['dtype']), attn_implementation='sdpa')
            if config['dtype'] == 'float16':
                stabilize_fp16(model)
            # CustomVoice never encodes reference audio. Keep its unused encoder off GPU.
            model.model.speech_tokenizer.model.encoder.to('cpu')
            model.model.generate = bounded_generate(model.model.generate)
            if config['device'].startswith('cuda'):
                torch.cuda.empty_cache()
        send({'ready': True, 'device': str(next(model.model.talker.parameters()).device),
              'decoder_device': str(next(model.model.speech_tokenizer.model.decoder.parameters()).device),
              'precision': 'FP16 + FP32 code predictor/codec' if config['dtype'] == 'float16' else config['dtype'],
              'speakers': model.get_supported_speakers()})
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        send({'error': str(exc)})
        return 1
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get('op') == 'close':
                break
            if request.get('op') != 'synthesize':
                raise ValueError('Unsupported operation')
            language = {'ja': 'Japanese', 'en': 'English'}[request['language']]
            with contextlib.redirect_stdout(sys.stderr), torch.inference_mode():
                if config['device'].startswith('cuda'):
                    torch.cuda.reset_peak_memory_stats()
                waves, rate = model.generate_custom_voice(
                    text=request['text'], language=language, speaker=request['speaker'],
                    max_new_tokens=config['max_new_tokens'])
                samples = np.asarray(waves[0], dtype='<f4').reshape(-1)
                if len(samples) == 0 or not np.isfinite(samples).all():
                    raise RuntimeError('Qwen TTS returned invalid audio')
            metrics = {}
            if config['device'].startswith('cuda'):
                metrics = {'allocated_peak_mib': torch.cuda.max_memory_allocated() / 1048576,
                           'reserved_peak_mib': torch.cuda.max_memory_reserved() / 1048576}
                torch.cuda.empty_cache()
            send({'cuda': metrics, 'rate': int(rate), 'samples': base64.b64encode(samples.tobytes()).decode('ascii')})
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            send({'error': str(exc)})
            if 'device-side assert' in str(exc):
                return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
