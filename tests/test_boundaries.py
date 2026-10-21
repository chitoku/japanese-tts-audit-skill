import unittest
from types import SimpleNamespace
import numpy as np
from tts_audit.core import align
from tts_audit.boundaries import reconcile
from tts_audit.cli import audio_intervals, boundary_recheck


class BoundaryTests(unittest.TestCase):
    def primary(self):
        return align('糾弾する。追加する。',[
            {'start_s':0,'end_s':4,'text':'キュー'},
            {'start_s':4,'end_s':8,'text':'キューダンスルツイカスル'}])

    def test_disappearing_difference_is_not_a_correct_verdict(self):
        first=self.primary()
        second=align('糾弾する。追加する。',[{'start_s':0,'end_s':8,'text':'キューダンスルツイカスル'}])
        checks=reconcile(first,second)
        self.assertEqual(checks[0]['status'],'not_reproduced')
        self.assertEqual(first['findings'][0]['review_priority'],'low_boundary')
        self.assertEqual(first['findings'][0]['status'],'unreviewed')
        self.assertTrue(first['findings'][0]['observed_kana'].startswith('キューキュー'))

    def test_true_error_remains(self):
        first=self.primary()
        second=align('糾弾する。追加する。',[{'start_s':0,'end_s':8,'text':'シュータンスルツイカスル'}])
        self.assertEqual(reconcile(first,second)[0]['status'],'persistent')
        self.assertEqual(first['findings'][0]['review_priority'],'normal')

    def test_missing_or_bad_context_cannot_clear_candidate(self):
        first=self.primary()
        second=align('糾弾する。追加する。',[{'start_s':0,'end_s':8,'text':'キューダンスルスイカスル'}])
        checks=reconcile(first,second)
        self.assertNotEqual(checks[0]['status'],'not_reproduced')
        self.assertEqual(first['findings'][0]['review_priority'],'normal')

    def test_shifted_intervals_cover_audio_and_avoid_old_cuts(self):
        audio=np.ones(62*16000,dtype='float32')
        cuts=[18,36,54]
        spans=list(audio_intervals(audio,18,first_seconds=9,avoid_boundaries=cuts))
        self.assertEqual(spans[0][0],0);self.assertEqual(spans[-1][1],len(audio))
        self.assertTrue(all(a[1]==b[0] for a,b in zip(spans,spans[1:])))
        self.assertTrue(all(abs(end/16000-cut)>=3 for _,end in spans[:-1] for cut in cuts))
        self.assertTrue(all(end-start<=28*16000 for start,end in spans))

    def test_failed_recheck_keeps_candidates(self):
        def fail(audio):raise RuntimeError('recognizer failed')
        args=SimpleNamespace(boundary_recheck=True,transcript_json=None,chunk_seconds=18)
        result=self.primary();result.update(script='糾弾する。追加する。',readings_override={})
        boundary_recheck(result,np.ones(8*16000,dtype='float32'),args,fail)
        self.assertEqual(result['boundary_recheck']['status'],'failed')
        self.assertTrue(result['findings'])
        self.assertNotEqual(result['findings'][0].get('review_priority'),'low_boundary')

    def test_import_does_not_silently_start_asr(self):
        args=SimpleNamespace(boundary_recheck=None,transcript_json='existing.json')
        result=self.primary()
        boundary_recheck(result,None,args)
        self.assertEqual(result['boundary_recheck']['status'],'disabled')

    def test_no_candidates_does_not_start_asr(self):
        args=SimpleNamespace(boundary_recheck=True,transcript_json=None)
        result={'findings':[]}
        boundary_recheck(result,None,args)
        self.assertEqual(result['boundary_recheck']['status'],'not_needed')
