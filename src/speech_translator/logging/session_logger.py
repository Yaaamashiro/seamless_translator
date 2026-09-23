import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class SessionLogger:
    def __init__(self, directory, enabled=True):
        self.enabled = enabled
        self.lock = threading.Lock()
        self.path = Path(directory) / f'session_{datetime.now():%Y%m%d_%H%M%S_%f}.jsonl'

    def write(self, record):
        if self.enabled:
            with self.lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps({'timestamp': datetime.now(timezone.utc).isoformat(),
                                             **record}, ensure_ascii=False) + '\n')
