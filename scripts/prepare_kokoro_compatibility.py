from pathlib import Path
p=Path('.venv-kokoro/Lib/site-packages/misaki/cutlet.py')
s=p.read_text(encoding='utf-8')
Path('artifacts/tts-comparison/cutlet-original.py').write_text(s,encoding='utf-8')
s=s.replace('import mojimoji\n','').replace('mojimoji.zen_to_han(text, kana=False)','jaconv.z2h(text, kana=False, ascii=True, digit=True)').replace('mojimoji.han_to_zen(text, digit=False, ascii=False)','jaconv.h2z(text, kana=True, digit=False, ascii=False)')
p.write_text(s,encoding='utf-8')
Path('artifacts/tts-comparison/cutlet-comparison.py').write_text(s,encoding='utf-8')
