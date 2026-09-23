from .process_tts import ProcessTTS

class KokoroTTS(ProcessTTS):
    model_filename = 'kokoro-v1_0.pth'
    worker_filename = 'kokoro_worker.py'
    label = 'Kokoro 82M'
