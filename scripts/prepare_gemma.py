"""Prepare only the selected Gemma E4B, independently of comparison artifacts."""
import json
from prepare_gemma_comparison import download, ROOT
if __name__ == '__main__':
    result = download('E4B')
    path = ROOT / 'models' / 'translation' / 'gemma4-e4b' / 'download.json'
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
