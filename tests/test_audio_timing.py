import copy
import unittest
from tts_audit.audio_timing import transcript_fingerprint, validate_audio_timing
from tts_audit.timeline_alignment import build_timeline_alignment


class AudioTimingTests(unittest.TestCase):
    def setUp(self):
        self.report={'run_id':'test','audio_sha256':'fixed-audio','duration_s':8,'script':'耳',
                     'reading_units':[dict(start=0,end=1,reading='ミミ')],
                     'findings':[dict(id='F001',script_start=0,script_end=1,observed_kana='ニ')]}
        self.transcript={'segments':[dict(start_s=0,end_s=8,text='ニ')]}
        self.timing={'schema_version':1,'method':'kana_whisper_token_attention_dtw','run_id':'test',
                     'audio_sha256':'fixed-audio','transcript_sha256':transcript_fingerprint(self.transcript),
                     'characters':[dict(text='ニ',start_s=3,end_s=3.5,source='attention_dtw')]}

    def test_audio_times_replace_uniform_estimate_without_changing_evidence(self):
        before=copy.deepcopy((self.report,self.transcript))
        aligned=build_timeline_alignment(self.report,self.transcript,self.timing)
        self.assertEqual(aligned['timing_status'],'accepted')
        self.assertEqual(aligned['findings']['F001']['start_s'],3)
        self.assertEqual(aligned['findings']['F001']['end_s'],3.5)
        self.assertEqual(aligned['script_tokens'][0]['text'],'耳')
        self.assertEqual(aligned['kana_chars'][0]['text'],'ニ')
        self.assertFalse(aligned['word_timestamps_verified'])
        self.assertEqual((self.report,self.transcript),before)

    def test_wrong_run_audio_or_transcript_falls_back_without_using_wrong_times(self):
        for field in ['run_id','audio_sha256','transcript_sha256','method']:
            timing=copy.deepcopy(self.timing);timing[field]='different'
            aligned=build_timeline_alignment(self.report,self.transcript,timing)
            with self.subTest(field=field):
                self.assertEqual(aligned['timing_status'],'rejected')
                self.assertEqual(aligned['findings']['F001']['start_s'],0)
                self.assertEqual(aligned['findings']['F001']['end_s'],8)

    def test_rejects_bad_character_text_bounds_and_nonfinite_values(self):
        for patch in [dict(text='ミ'),dict(start_s=-1),dict(end_s=9),dict(start_s=float('nan')),
                      dict(start_s=True),dict(start_s=4,end_s=3)]:
            timing=copy.deepcopy(self.timing);timing['characters'][0].update(patch)
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                validate_audio_timing(self.report,self.transcript,timing)
        timing=copy.deepcopy(self.timing);timing['characters']=[]
        with self.assertRaises(ValueError):validate_audio_timing(self.report,self.transcript,timing)

    def test_rejects_reversed_character_times(self):
        transcript={'segments':[dict(start_s=0,end_s=8,text='ニニ')]}
        timing=copy.deepcopy(self.timing);timing['transcript_sha256']=transcript_fingerprint(transcript)
        timing['characters']=[dict(text='ニ',start_s=3,end_s=4),dict(text='ニ',start_s=2,end_s=3)]
        with self.assertRaises(ValueError):validate_audio_timing(self.report,transcript,timing)


if __name__=='__main__':unittest.main()
