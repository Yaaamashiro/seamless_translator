"""Compatibility helpers for the pinned official qwen-tts 0.1.1 runtime."""
def cast_embedding_input(module, args, kwargs):
    embedding = kwargs.get('inputs_embeds')
    if embedding is not None:
        kwargs['inputs_embeds'] = embedding.to(next(module.parameters()).dtype)
    return args, kwargs


def stabilize_fp16(model):
    # GTX1650: the code predictor's MLP overflows FP16 before down_proj.
    # Keep this small predictor on the same GPU in FP32, and cast the
    # accumulated codec embeddings back to the main talker's dtype.
    model.model.speech_tokenizer.model.float()
    predictor = model.model.talker.code_predictor.float()
    predictor.register_forward_pre_hook(cast_embedding_input, with_kwargs=True)
    model.model.talker.model.register_forward_pre_hook(cast_embedding_input, with_kwargs=True)


def bounded_generate(generate):
    def checked(*args, **kwargs):
        codes, hidden = generate(*args, **kwargs)
        # Qwen omits the initial non-code step from returned codes. Reject
        # reaching that boundary rather than decoding a truncated utterance.
        if any(code.shape[0] >= kwargs['max_new_tokens'] - 1 for code in codes):
            raise RuntimeError('音声生成が上限に達しました。短い発話で再試行してください。')
        return codes, hidden
    return checked
