import unittest
from tts_audit.core import align,normalize
from tts_audit.cli import validate_segments, audio_intervals

class AuditTests(unittest.TestCase):
    def test_quiet_boundary_and_full_coverage(self):
        import numpy as np
        audio=np.full(14*16000,.2,dtype='float32');audio[6*16000:7*16000]=0
        parts=list(audio_intervals(audio,5))
        self.assertEqual(parts[0][0],0)
        self.assertTrue(6*16000<=parts[0][1]<=7*16000)
        self.assertEqual(parts[-1][1],len(audio))
        self.assertTrue(all(a[1]==b[0] for a,b in zip(parts,parts[1:])))
    def segment(self,text):return [{'start_s':0,'end_s':8,'text':text}]
    def test_long_vowels(self):
        self.assertEqual(normalize('増加分ゾウカブン')[0],normalize('ゾーカブン')[0])
        self.assertEqual(normalize('ケイコウ')[0],normalize('ケーコー')[0])
    def test_correct_and_particles(self):
        r=align('私は糾弾する。',self.segment('ワタシワキューダンスル'),{'私':'わたし'})
        self.assertEqual(r['findings'],[])
    def test_unknown_reading(self):
        r=align('糾弾する。',self.segment('シュータンスル'))
        self.assertTrue(any('糾弾' in f['surface'] and 'シュータン' in f['observed_kana'] for f in r['findings']),r)
    def test_outside_target(self):
        r=align('増加分が相殺される。',self.segment('ゾージャブンガソーサイサレル'))
        self.assertTrue(any('増加' in f['surface'] for f in r['findings']),r)
        self.assertFalse(any('相殺' in f['surface'] for f in r['findings']),r)
    def test_override(self):
        r=align('市場へ行く。',self.segment('イチバエイク'),{'市場':'いちば'})
        self.assertEqual(r['findings'],[])
    def test_deletion(self):
        r=align('糾弾する。',self.segment('スル'))
        self.assertTrue(r['findings'])
        self.assertEqual(r['findings'][0]['time_granularity'],'recognition_segment')
    def test_bad_timing(self):
        with self.assertRaises(ValueError):validate_segments({'segments':[{'text':'ア','start_s':0,'end_s':20}]},8)
        with self.assertRaises(ValueError):validate_segments({'segments':[{'text':'ア','start_s':1,'end_s':8}]},8)
        with self.assertRaises(ValueError):validate_segments({'segments':[{'text':'漢字','start_s':0,'end_s':8}]},8)
        with self.assertRaises(ValueError):validate_segments({'segments':[{'text':'','start_s':0,'end_s':8}]},8)
    def test_multiple_segments(self):
        r=align('糾弾する。相殺する。',[{'start_s':0,'end_s':4,'text':'キューダンスル'},{'start_s':4,'end_s':8,'text':'ソーサツスル'}])
        self.assertTrue(r['findings'])
        self.assertTrue(all(f['start_s']==4 and f['end_s']==8 for f in r['findings']),r)

if __name__=='__main__':unittest.main()
