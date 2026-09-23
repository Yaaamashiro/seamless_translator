"""Persistent Kokoro CUDA worker, isolated from the application's dependencies."""
import base64,contextlib,json,sys,traceback
from pathlib import Path

def send(value):
    print(json.dumps(value,ensure_ascii=False),flush=True)

def main():
    config=json.loads(sys.argv[1])
    # Avoid importing the adjacent app adapter instead of the installed kokoro package.
    sys.path=[p for p in sys.path if Path(p).resolve()!=Path(__file__).resolve().parent]
    try:
        with contextlib.redirect_stdout(sys.stderr):
            import numpy as np
            import torch
            import pyopenjtalk
            from kokoro import KModel,KPipeline
            torch.set_num_threads(2)
            if config['device'].startswith('cuda') and not torch.cuda.is_available():
                raise RuntimeError('Kokoro用CUDAが利用できません。CPUへ自動切替しません。')
            if config['dtype']!='float32':
                raise ValueError('Kokoroはfloat32を指定してください。')
            folder=Path(config['model_path'])
            model=KModel(repo_id='hexgrad/Kokoro-82M',config=str(folder/'config.json'),model=str(folder/'kokoro-v1_0.pth')).to(config['device']).eval()
            pipes={lang:KPipeline(lang_code=code,model=model,repo_id='hexgrad/Kokoro-82M') for lang,code in [('ja','j'),('en','a')]}
            voices={}
            for lang in ('ja','en'):
                speaker=config[lang+'_speaker']
                if Path(speaker).name!=speaker or not speaker.startswith('j' if lang=='ja' else ('a','b')):
                    raise ValueError('話者と言語が一致しません: '+speaker)
                voices[lang]=torch.load(folder/'voices'/(speaker+'.pt'),map_location='cpu',weights_only=True)
            device=str(next(model.parameters()).device)
            # Initialize both frontends/kernels before accepting the first utterance.
            with torch.inference_mode():
                for lang,text in [('ja','こんにちは。'),('en','Hello.')]:
                    list(pipes[lang](text,voice=voices[lang],speed=1))
            if device.startswith('cuda'):torch.cuda.empty_cache()
        send({'ready':True,'device':device,'decoder_device':device,'precision':'float32',
              'speakers':[config['ja_speaker'],config['en_speaker']]})
    except Exception as exc:
        traceback.print_exc(file=sys.stderr);send({'error':str(exc)});return 1
    for line in sys.stdin:
        try:
            request=json.loads(line)
            if request.get('op')=='close':break
            if request.get('op')!='synthesize':raise ValueError('Unsupported operation')
            lang=request['language'];text=request['text']
            if lang not in pipes or not text.strip() or len(text)>2000:raise ValueError('Invalid text/language')
            with contextlib.redirect_stdout(sys.stderr),torch.inference_mode():
                if device.startswith('cuda'):torch.cuda.reset_peak_memory_stats()
                # Resolve counters in context before Cutlet splits digits and nouns.
                spoken=pyopenjtalk.g2p(text,kana=True) if lang=='ja' else text
                phonemes=pipes[lang].g2p(spoken)[0]
                if not phonemes or len(phonemes)>510:
                    raise ValueError('発話が長すぎるか読みへ変換できません。短い発話で再試行してください。')
                chunks=list(pipes[lang](spoken,voice=voices[lang],speed=1))
                samples=np.concatenate([x.audio.cpu().numpy() for x in chunks]).astype('<f4')
                if not len(samples) or not np.isfinite(samples).all():raise RuntimeError('Invalid audio')
            metrics={}
            if device.startswith('cuda'):
                metrics={'allocated_peak_mib':torch.cuda.max_memory_allocated()/1048576,'reserved_peak_mib':torch.cuda.max_memory_reserved()/1048576}
                torch.cuda.empty_cache()
            send({'rate':24000,'samples':base64.b64encode(samples.tobytes()).decode('ascii'),'cuda':metrics,'spoken_text':spoken})
        except Exception as exc:
            traceback.print_exc(file=sys.stderr);send({'error':str(exc)})
            if 'device-side assert' in str(exc):return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
