import unittest
from tts_audit.timeline_alignment import build_timeline_alignment


class TimelineAlignmentTests(unittest.TestCase):
    def report(self):
        return {'duration_s': 8, 'script': '荷に耳を寄せる', 'reading_units': [
            dict(start=0,end=1,reading='ニ'), dict(start=1,end=2,reading='ニ'),
            dict(start=2,end=3,reading='ミミ'), dict(start=3,end=4,reading='オ'),
            dict(start=4,end=7,reading='ヨセル')], 'findings': [
            dict(id='F001',script_start=2,script_end=3,observed_kana='ニ')]}

    def test_repeated_kana_highlights_the_aligned_occurrence(self):
        a = build_timeline_alignment(self.report(), {'segments': [dict(start_s=0,end_s=8,text='ニニニオヨセル')]})
        marked = [i for i,ch in enumerate(a['kana_chars']) if ch['finding_ids']]
        self.assertEqual(marked, [2])
        tokens = [u for u in a['script_tokens'] if u['finding_ids']]
        self.assertEqual([u['text'] for u in tokens], ['耳'])
        self.assertFalse(a['word_timestamps_verified'])

    def test_time_projection_respects_asr_segment_boundaries(self):
        r = {'duration_s': 12, 'script': '雨。耳。', 'reading_units': [
            dict(start=0,end=1,reading='アメ'),dict(start=1,end=2,reading='。'),
            dict(start=2,end=3,reading='ミミ'),dict(start=3,end=4,reading='。')],
            'findings': [dict(id='F002',script_start=2,script_end=3,observed_kana='ニ')]}
        a = build_timeline_alignment(r, {'segments': [dict(start_s=0,end_s=2,text='アメ'),dict(start_s=9,end_s=12,text='ニ')]})
        self.assertGreaterEqual(a['findings']['F002']['start_s'],9)
        self.assertLessEqual(a['findings']['F002']['end_s'],12)
        self.assertEqual(''.join(c['text'] for c in a['kana_chars'] if 'F002' in c['finding_ids']),'ニ')

    def test_missing_alignment_does_not_invent_verified_timestamps(self):
        a = build_timeline_alignment({'duration_s': 10, 'script': '未解析', 'findings': []}, {})
        self.assertEqual(a['script_tokens'],[])
        self.assertEqual(a['kana_chars'],[])
        self.assertFalse(a['word_timestamps_verified'])

    def test_extra_syllables_from_original_finding_remain_highlighted(self):
        r = {'duration_s': 3, 'script': '見えない', 'reading_units': [
            dict(start=0,end=2,reading='ミエ'),dict(start=2,end=4,reading='ナイ')],
            'findings':[dict(id='F001',script_start=2,script_end=4,observed_kana='ンミエナイ')]}
        a=build_timeline_alignment(r,{'segments':[dict(start_s=0,end_s=3,text='ンミエナイ')]})
        self.assertEqual(''.join(c['text'] for c in a['kana_chars'] if c['finding_ids']),'ンミエナイ')


if __name__=='__main__':unittest.main()
