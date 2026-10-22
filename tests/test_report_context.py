import unittest
from tts_audit.report import finding_context

class ReportContextTests(unittest.TestCase):
    def test_exact_repeated_character_occurrence(self):
        script='確認しました。風の弱い時間帯を選んで作業しました。'
        start=script.index('し',script.index('作業'))
        html=finding_context(script,dict(surface='し',script_start=start,script_end=start+1))
        self.assertIn('作業<mark>し</mark>ました',html)
        self.assertNotIn('確認',html)

    def test_wrong_or_missing_offsets_do_not_invent_location(self):
        self.assertEqual(finding_context('作業しました。',dict(surface='し',script_start=0,script_end=1)),'')
        self.assertEqual(finding_context('作業しました。',dict(surface='し')),'')

    def test_context_and_surface_are_html_escaped(self):
        html=finding_context('<script>し&ました',dict(surface='し',script_start=8,script_end=9))
        self.assertIn('&lt;script&gt;<mark>し</mark>&amp;ました',html)
        self.assertNotIn('<script>',html)

if __name__=='__main__':unittest.main()
