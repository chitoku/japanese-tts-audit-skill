import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import soundfile as sf
from tts_audit.cli import check, transcribe
from tts_audit.audio_timing import project_audio_timing, validate_audio_timing


class FakeRecognizer:
    def __init__(self, fail=False): self.fail=fail; self.timed_calls=0; self.plain_calls=0
    def metadata(self): return {'model':'test'}
    def __call__(self,audio): self.plain_calls+=1; return 'ニ'
    def timed(self,audio):
        self.timed_calls+=1
        if self.fail: raise RuntimeError('unsupported')
        return {'text':'ニ','groups':[{'text':'ニ','start_s':.3,'end_s':.6}]}


class CliTimingTests(unittest.TestCase):
    def args(self,root,**kwargs):
        a=dict(audio=root/'in.wav',script=root/'script.txt',out=root/'out',readings=None,
               transcript_json=None,cache_dir=None,offline=True,device='cpu',chunk_seconds=18,boundary_recheck=False,timestamps=True)
        a.update(kwargs);return SimpleNamespace(**a)

    def test_default_timed_decode_once_and_fallback(self):
        args=SimpleNamespace(chunk_seconds=18)
        for fail in (False,True):
            rec=FakeRecognizer(fail);doc=transcribe(np.zeros(16000),args,rec)
            self.assertEqual(rec.timed_calls,1);self.assertEqual(rec.plain_calls,int(fail))
            self.assertEqual(doc['recognition']['audio_timing_status'],'failed' if fail else 'completed')
            self.assertEqual('timing_segments' in doc,not fail)
        rec=FakeRecognizer();doc=transcribe(np.zeros(16000),args,rec,with_timing=False)
        self.assertEqual(rec.timed_calls,0);self.assertNotIn('timing_segments',doc)

    def test_cli_outputs_audio_timing_and_static_timeline_without_overwriting(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);sf.write(root/'in.wav',np.zeros(16000),16000);(root/'script.txt').write_text('耳')
            args=self.args(root);rec=FakeRecognizer();self.assertEqual(check(args,rec),0)
            report=json.loads((args.out/'report.json').read_text());transcript=json.loads((args.out/'transcript.json').read_text());timing=json.loads((args.out/'audio-timing.json').read_text())
            self.assertEqual(report['source_files'],{'audio':str(args.audio.resolve()),'script':str(args.script.resolve())})
            self.assertEqual(validate_audio_timing(report,transcript,timing)[0]['start_s'],.3)
            self.assertIn('"timing_status": "accepted"',(args.out/'timeline.html').read_text())
            marker=args.out/'review-state.json';marker.write_text('saved judgments')
            with self.assertRaises(ValueError):check(args,rec)
            self.assertEqual(marker.read_text(),'saved judgments')

    def test_disable_failure_and_import_use_approximate_timeline(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);sf.write(root/'in.wav',np.zeros(16000),16000);(root/'script.txt').write_text('耳')
            imp=root/'import.json';imp.write_text(json.dumps({'audio_sha256':hashlib.sha256((root/'in.wav').read_bytes()).hexdigest(),'segments':[dict(text='ニ',start_s=0,end_s=1)]}))
            for label,kwargs,rec in [('disabled',dict(timestamps=False),FakeRecognizer()),('failed',{},FakeRecognizer(True)),('import',dict(transcript_json=imp),FakeRecognizer())]:
                args=self.args(root,out=root/label,**kwargs);check(args,rec)
                self.assertFalse((args.out/'audio-timing.json').exists())
                self.assertIn('"timing_status": "absent"',(args.out/'timeline.html').read_text())
                if label!='failed':self.assertEqual(rec.timed_calls,0)

    def test_projection_preserves_changed_original_text_and_rejects_low_coverage(self):
        report=dict(run_id='r',audio_sha256='a',duration_s=2)
        transcript={'segments':[dict(text='アイウ',start_s=0,end_s=2)]};original=copy.deepcopy(transcript)
        timed=[dict(text='アイウ',groups=[dict(text='アイ',start_s=.2,end_s=.8),dict(text='ウ',start_s=1,end_s=1.2)])]
        timing=project_audio_timing(report,transcript,timed)
        self.assertEqual(timing['characters'][0]['source'],'within_token_interpolation')
        self.assertEqual(transcript,original)
        changed={'segments':[dict(text='アイウエオカキクケコ',start_s=0,end_s=2)]}
        timed_changed=[dict(text='アイウエオサキクケコ',groups=[dict(text='アイウエオサキクケコ',start_s=.1,end_s=1.9)])]
        result=project_audio_timing(report,changed,timed_changed)
        self.assertEqual(''.join(ch['text'] for ch in result['characters']),changed['segments'][0]['text'])
        self.assertEqual(result['characters'][5]['source'],'unmatched_or_punctuation_interpolation')
        with self.assertRaises(ValueError):project_audio_timing(report,transcript,[dict(text='カキク',groups=[dict(text='カキク',start_s=.2,end_s=1)])])
