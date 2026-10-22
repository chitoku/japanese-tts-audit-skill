import json
from pathlib import Path
import unittest
from tts_audit.core import align, normalize
from tts_audit.report import render


class ReadingVariantTests(unittest.TestCase):
    def check(self, text, kana, readings=None):
        return align(text, [{'text':kana, 'start_s':0, 'end_s':8}], readings)

    def test_equivalent_notation_preserves_offsets_and_real_sound_differences(self):
        norm, offsets = normalize('つづく・ヂ')
        self.assertEqual(norm, 'ツズクジ')
        self.assertEqual(offsets, [0,1,2,4])
        for expected, actual in [('ジュンシュ','ジュンシ'),('ギネン','ニネン'),('マドグチ','マドブチ')]:
            self.assertNotEqual(normalize(expected)[0],normalize(actual)[0])

    def test_known_alternate_reading_remains_playable_and_unreviewed(self):
        for text,kana in [('払拭する。','フッシキスル'),('施工する。','セコースル'),('私がいう。','ワタシガユウ')]:
            with self.subTest(text=text):
                findings=self.check(text,kana)['findings']
                self.assertTrue(findings)
                for f in findings:
                    self.assertEqual(f['review_priority'],'low_variant')
                    self.assertEqual(f['status'],'unreviewed')
                    self.assertEqual((f['start_s'],f['end_s']),(0,8))

    def test_explicit_reading_difference_keeps_priority(self):
        r=self.check('払拭する。','フッシキスル',{'払拭':'ふっしょく'})
        f=r['findings'][0]
        self.assertNotEqual(f.get('review_priority'),'low_variant')
        self.assertTrue(f['reading_variant']['explicit_reading_difference'])
        self.assertEqual(f['expected_kana'],'ふっしょく')

    def test_unrelated_word_or_damaged_variant_cannot_be_downgraded(self):
        for text,kana in [('私語を慎む。','ワタシゴオツツシム'),('払拭する。','フッシスル'),('糾弾する。','シュータンスル')]:
            with self.subTest(text=text):
                findings=self.check(text,kana)['findings']
                self.assertTrue(findings)
                self.assertFalse(any(f.get('review_priority')=='low_variant' for f in findings))

    def test_variant_section_preserves_cards_and_explicit_difference_is_primary(self):
        for overrides,low in [(None,True),({'払拭':'ふっしょく'},False)]:
            r=self.check('払拭する。','フッシキスル',overrides)
            r.update(run_id='test',script='払拭する。',duration_s=8,recognition={'mode':'saved kana'})
            page=render(r)
            from html.parser import HTMLParser
            class CardParser(HTMLParser):
                def __init__(self):super().__init__();self.in_details=False;self.card_in_details=None
                def handle_starttag(self,tag,attrs):
                    if tag=='details':self.in_details=True
                    if tag=='article':self.card_in_details=self.in_details
                def handle_endtag(self,tag):
                    if tag=='details':self.in_details=False
            parser=CardParser();parser.feed(page)
            self.assertEqual(parser.card_in_details,low)

    def test_replay_preserves_all_fifteen_human_supported_errors(self):
        samples=json.loads((Path(__file__).parent/'fixtures/voicevox_reviewed_spans.json').read_text())
        checked=0
        for sample in samples:
            result=align(sample['script'],sample['segments'],sample['readings'])
            priority=[f for f in result['findings'] if f.get('review_priority')!='low_variant']
            for gold in sample['error_spans']:
                checked+=1
                self.assertTrue(any(f['script_start']<gold['script_end'] and f['script_end']>gold['script_start'] for f in priority),sample['id'])
        self.assertEqual(checked,15)
