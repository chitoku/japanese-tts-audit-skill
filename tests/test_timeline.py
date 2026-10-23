import json
import tempfile
from pathlib import Path
import unittest
from tts_audit.timeline import render_timeline
from tts_audit.server import ReviewStore, Conflict
from tts_audit.reviews import merge_notes


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.report = {'run_id': 'timeline', 'duration_s': 10, 'findings': []}
        (self.root / 'report.json').write_text(json.dumps(self.report))
        self.store = ReviewStore(self.root)
        self.annotation = {'id': 'M-example', 'kind': 'manual_flag', 'start_s': 2, 'end_s': 4,
                           'created_at': '2026-10-22T10:00:00Z'}
        self.note = {'verdict': 'error', 'heard': 'べー', 'note': '米の読み',
                     'updated_at': '2026-10-22T10:01:00Z'}

    def test_manual_flag_roundtrip_keeps_report_and_survives_legacy_save(self):
        raw = (self.root / 'report.json').read_bytes()
        payload = {'schema_version': 1, 'run_id': 'timeline', 'revision': 0,
                   'annotations': [self.annotation], 'notes': {'M-example': self.note}}
        state = self.store.update(payload)
        self.assertEqual(state['manual_candidate_count'], 1)
        self.assertEqual(state['candidate_count'], 1)
        self.assertEqual(state['unreviewed_count'], 0)
        self.assertEqual(ReviewStore(self.root).read(), state)
        later = self.store.update({'schema_version': 1, 'run_id': 'timeline', 'revision': 1, 'notes': {}})
        self.assertEqual(later['annotations'], [self.annotation])
        self.assertEqual(later['notes']['M-example'], self.note)
        self.assertEqual((self.root / 'report.json').read_bytes(), raw)
        with self.assertRaises(Conflict): self.store.update(payload)

    def test_ranges_are_not_counted_as_candidate_verdicts(self):
        annotation = dict(self.annotation, id='S-example', kind='reviewed_range')
        state = self.store.update({'schema_version': 1, 'run_id': 'timeline', 'revision': 0,
                                  'annotations': [annotation], 'notes': {}})
        self.assertEqual(state['candidate_count'], 0)
        self.assertEqual(state['annotations'], [annotation])

    def test_rejects_invalid_annotation_bounds_kinds_and_unknown_notes(self):
        for patch in ({'start_s': -1}, {'end_s': 11}, {'end_s': 2}, {'start_s': float('nan')},
                      {'start_s': True}, {'kind': 'invented'}, {'id': 'F001'},
                      {'created_at': 'yesterday'}):
            payload = {'schema_version': 1, 'run_id': 'timeline', 'revision': 0,
                       'annotations': [dict(self.annotation, **patch)], 'notes': {}}
            with self.subTest(patch=patch), self.assertRaises(ValueError): self.store.update(payload)
        with self.assertRaises(ValueError):
            self.store.update({'schema_version': 1, 'run_id': 'timeline', 'revision': 0,
                               'notes': {'M-unknown': self.note}})
        self.assertEqual(self.store.read()['revision'], 0)

    def test_export_import_preserves_manual_evidence(self):
        batch = {'schema_version': 1, 'run_id': 'timeline', 'exported_at': '2026-10-22T10:01:00Z',
                 'annotations': [self.annotation], 'notes': {'M-example': self.note}}
        merged = merge_notes(self.report, batch)
        self.assertEqual(merged['annotations'], [self.annotation])
        self.assertEqual(merged['notes']['M-example'], self.note)

    def test_embedded_untrusted_script_cannot_close_script_element(self):
        data = dict(self.report, script='</script><script>alert(1)</script>')
        page = render_timeline(data)
        self.assertNotIn('</script><script>alert(1)', page)
        self.assertIn('\\u003c/script\\u003e', page)
        self.assertIn('文字列照合', page)


if __name__ == '__main__': unittest.main()
