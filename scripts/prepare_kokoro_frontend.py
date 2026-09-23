"""Reproducible compatibility patch for misaki 0.9.4 on Windows/Python 3.13."""
from pathlib import Path
import importlib.util
spec=importlib.util.find_spec('misaki')
p=Path(spec.origin).with_name('cutlet.py')
s=p.read_text(encoding='utf-8')
if 'import mojimoji' in s:
    expected=['mojimoji.zen_to_han(text, kana=False)','mojimoji.han_to_zen(text, digit=False, ascii=False)']
    if not all(x in s for x in expected):raise RuntimeError('Unsupported misaki version')
    s=s.replace('import mojimoji\n','').replace(expected[0],'jaconv.z2h(text, kana=False, ascii=True, digit=True)').replace(expected[1],'jaconv.h2z(text, kana=True, digit=False, ascii=False)')
    p.write_text(s,encoding='utf-8')
from misaki.ja import JAG2P
import pyopenjtalk
reading=pyopenjtalk.g2p('2階',kana=True)
assert reading=='ニカイ',reading
assert 'kai' in JAG2P()(reading)[0]
print('Kokoro Japanese frontend ready')
