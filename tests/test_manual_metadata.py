import json
from pathlib import Path
import tempfile
import unittest
from tts_audit.server import ReviewStore


class ManualMetadataTests(unittest.TestCase):
    def test_delete_restore_roundtrip_keeps_record_and_counts(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);raw=json.dumps(dict(run_id='m',duration_s=10,findings=[]));(p/'report.json').write_text(raw)
            store=ReviewStore(p);annotation=dict(id='M-a',kind='manual_flag',start_s=2,end_s=5,created_at='2026-10-22T00:00:00Z')
            note=dict(verdict='error',heard='しゅうたん',note='台本との差',target_text='糾弾',expected_reading='きゅうだん',updated_at='2026-10-22T00:00:01Z')
            def save(n):return store.update(dict(schema_version=1,run_id='m',revision=store.read()['revision'],annotations=[annotation],notes={'M-a':n}))
            s=save(note);self.assertEqual(s['manual_candidate_count'],1)
            deleted=save(dict(note,deleted=True,updated_at='2026-10-22T00:00:02Z'))
            self.assertEqual(deleted['candidate_count'],0);self.assertEqual(deleted['reviewed_count'],0);self.assertEqual(deleted['unreviewed_count'],0)
            self.assertEqual(ReviewStore(p).read()['notes']['M-a']['target_text'],'糾弾')
            # An omitted annotation in an older client does not resurrect the deleted flag.
            legacy=store.update(dict(schema_version=1,run_id='m',revision=deleted['revision'],notes={}))
            self.assertEqual(legacy['candidate_count'],0)
            restored=save(dict(note,deleted=False,updated_at='2026-10-22T00:00:03Z'))
            self.assertEqual(restored['candidate_count'],1);self.assertEqual(restored['reviewed_count'],1)
            self.assertEqual((p/'report.json').read_text(),raw)

    def test_rejects_invalid_manual_metadata(self):
        from tts_audit.reviews import merge_notes
        report=dict(run_id='r',duration_s=10,findings=[dict(id='F001')])
        for patch in [dict(deleted='yes'),dict(target_text=3),dict(expected_reading=['x'])]:
            batch=dict(schema_version=1,run_id='r',exported_at='2026-10-22T00:00:02Z',notes={'F001':dict(verdict='error',heard='',note='',updated_at='2026-10-22T00:00:01Z',**patch)})
            with self.assertRaises(ValueError):merge_notes(report,batch)
