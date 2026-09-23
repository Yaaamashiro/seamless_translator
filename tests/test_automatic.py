import threading,time,unittest
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock,patch
import numpy as np
from speech_translator.config import DEFAULTS
from speech_translator.audio.vad import SpeechSegmenter, StreamingVAD
from speech_translator.pipeline.automatic import AutomaticConversation
from speech_translator.pipeline.channel import ChannelState

class SegmenterTests(unittest.TestCase):
    def setUp(self):
        self.config=deepcopy(DEFAULTS['automatic'])
        self.config.update(start_ms=64,min_speech_ms=128,silence_ms=96,pre_roll_ms=64,max_utterance_seconds=1)
        self.s=SpeechSegmenter(self.config)
    def feed(self,n,p,value=1):
        return [self.s.feed(np.full(512,value,dtype='float32'),p) for _ in range(n)]
    def test_preroll_and_end_of_utterance(self):
        self.feed(4,0,value=.1)
        self.assertEqual(self.feed(2,.9)[-1][0],'start')
        self.feed(4,.9)
        self.assertIsNone(self.feed(2,0)[-1][0])
        event,audio=self.feed(1,0)[-1]
        self.assertEqual(event,'end')
        self.assertEqual(audio.sample_rate,16000)
        self.assertAlmostEqual(float(audio.samples[0]),.1)
    def test_transient_noise_and_short_burst_do_not_translate(self):
        self.assertIsNone(self.feed(1,.9)[-1][0])
        self.feed(2,0)
        self.feed(2,.9)
        self.assertEqual(self.feed(3,0)[-1][0],'discard')
    def test_long_speech_is_bounded_and_waits_for_silence(self):
        events=self.feed(50,.9)
        self.assertEqual(sum(e=='too_long' for e,_ in events),1)
        self.assertEqual(len(self.s.chunks),0)
        self.assertTrue(self.s.active)
        self.assertEqual(self.feed(3,0)[-1][0],'discard')

class FakeVAD:
    def __init__(self,session):pass
    def reset(self):pass
    def probability(self,frame):return float(np.max(frame)>.2)

class FakeStream:
    instances=[]
    def __init__(self,device,callback,**kwargs):
        self.device=device;self.callback=callback;self.active=False;self.closed=False
        self.instances.append(self)
    def start(self):self.active=True
    def abort(self):self.active=False
    def close(self):self.closed=True
    def push(self,value):
        self.callback(np.full((512,1),value,dtype='float32'),512,SimpleNamespace(currentTime=1,inputBufferAdcTime=1),False)

class AutomaticTests(unittest.TestCase):
    def setUp(self):
        FakeStream.instances=[]
        self.config=deepcopy(DEFAULTS)
        self.config['automatic'].update(start_ms=64,min_speech_ms=96,silence_ms=96,pre_roll_ms=64,playback_guard_ms=180)
        self.release=threading.Event();self.playing=threading.Event();self.calls=[];self.notifications=[]
        self.channels={}
        for i,key in enumerate(['A_TO_B','B_TO_A']):
            c=SimpleNamespace(input_device=i,state=ChannelState.IDLE,executor=ThreadPoolExecutor(max_workers=1),cancelled=threading.Event(),emit=Mock(),player=Mock())
            c.player.cancel.side_effect=self.release.set
            c.set_state=lambda state,c=c:setattr(c,'state',state)
            def process(audio,key=key,c=c):
                self.calls.append(key);c.set_state(ChannelState.PLAYING);self.playing.set()
                self.release.wait(timeout=3);c.set_state(ChannelState.IDLE)
            c.process=process;self.channels[key]=c
        self.patches=[patch('speech_translator.pipeline.automatic.StreamingVAD',FakeVAD),patch('speech_translator.pipeline.automatic.sd.InputStream',FakeStream),patch('speech_translator.pipeline.automatic.sd.query_devices',return_value={'default_samplerate':16000,'max_input_channels':1}),patch('faster_whisper.vad.get_vad_model',return_value=Mock())]
        for p in self.patches:p.start()
        self.auto=AutomaticConversation(self.channels,self.config,lambda *v:self.notifications.append(v))
    def wait(self,predicate):
        end=time.monotonic()+3
        while not predicate() and time.monotonic()<end:time.sleep(.005)
        self.assertTrue(predicate())
    def utterance(self,index):
        for value in [1]*6+[0]*4:
            FakeStream.instances[index].push(value);time.sleep(.006)
    def tearDown(self):
        self.auto.stop()
        if self.auto.future:self.auto.future.result(timeout=4)
        for c in self.channels.values():c.executor.shutdown(wait=True)
        for p in reversed(self.patches):p.stop()
    def test_playback_and_tail_cannot_queue_echo_then_peer_can_speak(self):
        self.auto.start();self.wait(self.auto.accepting.is_set)
        self.utterance(0);self.wait(self.playing.is_set)
        self.assertFalse(self.auto.accepting.is_set())
        self.utterance(1)
        self.assertTrue(self.auto.queue.empty())
        self.release.set()
        self.wait(lambda:any('余韻' in msg for _,msg in self.notifications))
        self.utterance(1)
        self.assertEqual(self.calls,['A_TO_B'])
        self.wait(self.auto.accepting.is_set)
        self.utterance(1);self.wait(lambda:len(self.calls)==2)
        self.assertEqual(self.calls,['A_TO_B','B_TO_A'])
    def test_stop_discards_partial_speech_and_closes_both_streams(self):
        self.auto.start();self.wait(self.auto.accepting.is_set)
        for _ in range(3):FakeStream.instances[0].push(1);time.sleep(.01)
        self.auto.stop();self.auto.future.result(timeout=3)
        self.assertEqual(self.calls,[])
        self.assertTrue(all(s.closed for s in FakeStream.instances))
        self.assertFalse(self.notifications[-1][0])
    def test_second_input_start_failure_closes_first_input(self):
        original=FakeStream.start
        def start(s):
            if s.device==1:raise RuntimeError('disconnected')
            original(s)
        with patch.object(FakeStream,'start',start):
            self.auto.start().result(timeout=3)
        self.assertTrue(all(s.closed for s in FakeStream.instances))
        self.assertIn('disconnected',self.notifications[-1][1])
    def test_stale_input_and_overflow_are_not_translated(self):
        self.auto.start();self.wait(self.auto.accepting.is_set)
        FakeStream.instances[0].callback(np.ones((512,1),dtype='float32'),512,SimpleNamespace(currentTime=10,inputBufferAdcTime=1),False)
        self.assertTrue(self.auto.queue.empty())
        self.auto.capture_error='overflow'
        self.auto.future.result(timeout=3)
        self.assertEqual(self.calls,[])
        self.assertIn('overflow',self.notifications[-1][1])
