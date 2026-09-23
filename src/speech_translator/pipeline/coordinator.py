import threading

from speech_translator.pipeline.channel import Channel, ChannelState


class Coordinator:
    """MVP turn-taking: hold the turn through playback to prevent feedback."""
    def __init__(self, channels):
        self.channels = channels
        self.lock = threading.RLock()

    def toggle(self, direction):
        with self.lock:
            peer_busy = any(c.state not in (ChannelState.IDLE, ChannelState.ERROR)
                            for key, c in self.channels.items() if key != direction)
            if not peer_busy:
                self.channels[direction].toggle()

    def close(self):
        return [channel.close() for channel in self.channels.values()]


def build_channels(selected, engines, config, logger, notify=lambda event: None):
    asr, translator, tts = engines
    return {direction: Channel(direction, selected[mic].index, selected[speaker].index,
                               source, target, asr, translator, tts, config, logger, notify)
            for direction, mic, speaker, source, target in [
                ('A_TO_B', 'mic_a', 'speaker_b', 'ja', 'en'),
                ('B_TO_A', 'mic_b', 'speaker_a', 'en', 'ja')]}
