import threading


class OpusTranslator:
    def __init__(self, config, progress=lambda message: None):
        from transformers import MarianMTModel, MarianTokenizer
        self.models = {}
        self.lock = threading.Lock()
        for source, target, key in [('ja', 'en', 'ja_en_model'), ('en', 'ja', 'en_ja_model')]:
            progress(f'{source.upper()}→{target.upper()} Translator: ロード中')
            tokenizer = MarianTokenizer.from_pretrained(config[key])
            model = MarianMTModel.from_pretrained(config[key]).eval()
            self.models[source, target] = tokenizer, model
            progress(f'✓ {source.upper()}→{target.upper()} Translator')

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        import torch
        if not text.strip():
            raise ValueError('翻訳対象が空です。')
        tokenizer, model = self.models[source_language, target_language]
        with self.lock, torch.inference_mode():
            encoded = tokenizer(text, return_tensors='pt', truncation=False)
            if encoded['input_ids'].shape[1] > 500:
                raise ValueError('発話が長すぎます。短い文に分けて録音してください。')
            output = model.generate(**encoded, max_new_tokens=512, num_beams=4)
            return tokenizer.decode(output[0], skip_special_tokens=True).strip()
