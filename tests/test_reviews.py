import unittest
from tts_audit.reviews import merge_notes
from tts_audit.report import render


class ReviewTests(unittest.TestCase):
    def batch(self, heard='ア', when='2026-10-21T05:00:00Z'):
        return {'schema_version': 1, 'run_id': 'one', 'exported_at': when,
                'notes': {'F001': {'verdict': 'error', 'heard': heard, 'note': '', 'updated_at': when}}}

    def test_wrong_run_and_unknown_id(self):
        report = {'run_id': 'one', 'findings': [{'id': 'F001'}]}
        batch = self.batch(); batch['run_id'] = 'two'
        with self.assertRaises(ValueError): merge_notes(report, batch)
        batch = self.batch(); batch['notes']['F999'] = batch['notes'].pop('F001')
        with self.assertRaises(ValueError): merge_notes(report, batch)

    def test_preserve_newer_and_blank(self):
        report = {'run_id': 'one', 'findings': [{'id': 'F001'}]}
        merged = merge_notes(report, self.batch(), self.batch('', '2026-10-21T06:00:00Z'))
        self.assertEqual(merged['notes']['F001']['heard'], '')

    def test_equal_timestamp_conflict(self):
        report = {'run_id': 'one', 'findings': [{'id': 'F001'}]}
        with self.assertRaises(ValueError): merge_notes(report, self.batch('ア'), self.batch('イ'))

    def test_seed_cannot_close_script(self):
        report = {'run_id': 'one', 'findings': [], 'reading_warnings': [],
                  'alignment_equal_fraction': 1, 'duration_s': 1, 'recognition': {'mode': 'local'},
                  'script': '', 'expected_kana': '', 'observed_kana': ''}
        html = render(report, self.batch('</script><script>alert(1)</script>'))
        self.assertEqual(html.count('<script>'), 1)
        self.assertIn('\\u003c/script', html)
