import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tts_audit.server import Conflict, ReviewStore, make_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.report = {'run_id': 'one', 'findings': [
            {'id': 'F001', 'surface': '糾弾', 'expected_kana': 'キューダン', 'observed_kana': 'シュータン',
             'start_s': 0, 'end_s': 1, 'reason': 'difference'},
            {'id': 'F002', 'surface': '何', 'expected_kana': 'ナニ', 'observed_kana': 'ナン',
             'start_s': 1, 'end_s': 2, 'reason': 'difference'}],
            'reading_warnings': [], 'alignment_equal_fraction': 1, 'duration_s': 2,
            'recognition': {'mode': 'imported'}, 'script': '糾弾。何。',
            'expected_kana': 'キューダンナニ', 'observed_kana': 'シュータンナン'}
        (self.root / 'report.json').write_text(json.dumps(self.report), encoding='utf-8')
        (self.root / 'audio.wav').write_bytes(b'0123456789')
        (self.root / 'transcript.json').write_text('{}')
        self.server = make_server(self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
        self.thread.start(); self.addCleanup(self.stop)
        self.url = self.server.review_url

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)

    def payload(self, revision=0, heard='しゅうたん', when='2026-10-21T12:00:00Z'):
        return {'schema_version': 1, 'run_id': 'one', 'revision': revision,
                'notes': {'F001': {'verdict': 'error', 'heard': heard, 'note': '', 'updated_at': when}}}

    def request(self, path='api/reviews', payload=None, headers=None):
        request = Request(self.url + path, data=None if payload is None else json.dumps(payload).encode(),
                          headers={'Content-Type': 'application/json', **(headers or {})})
        return urlopen(request, timeout=3)

    def post(self, payload, path='api/reviews'):
        with self.request(path, payload) as response: return json.load(response)

    def test_save_complete_edit_restart_and_asr_preservation(self):
        original = (self.root / 'report.json').read_bytes()
        state = self.post(self.payload())
        self.assertEqual(state['status'], 'draft'); self.assertEqual(state['revision'], 1)
        self.assertEqual(json.loads((self.root / 'review-state.json').read_text()), state)
        done = self.post(self.payload(1), 'api/complete')
        self.assertEqual(done['status'], 'completed'); self.assertEqual(done['unreviewed_count'], 1)
        self.assertIsNotNone(done['completed_at'])
        later = self.post(self.payload(2, heard='シュウタン', when='2026-10-21T12:01:00Z'))
        self.assertEqual(later['status'], 'draft'); self.assertIsNone(later['completed_at'])
        self.assertEqual(ReviewStore(self.root).read(), later)
        self.assertEqual((self.root / 'report.json').read_bytes(), original)

    def test_stale_tab_cannot_overwrite(self):
        self.post(self.payload())
        with self.assertRaises(HTTPError) as error: self.post(self.payload(0, heard='古い画面'))
        self.assertEqual(error.exception.code, 409)
        self.assertEqual(self.server.review_store.read()['notes']['F001']['heard'], 'しゅうたん')

    def test_concurrent_writes_accept_only_one_revision(self):
        results = []
        def update():
            try: self.server.review_store.update(self.payload()); results.append('saved')
            except Conflict: results.append('conflict')
        threads = [threading.Thread(target=update) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertCountEqual(results, ['saved', 'conflict'])

    def test_bad_run_unknown_candidate_and_invalid_fields_do_not_save(self):
        batches = [self.payload() for _ in range(4)]
        batches[0]['run_id'] = 'other'
        batches[1]['notes']['F999'] = batches[1]['notes'].pop('F001')
        batches[2]['notes']['F001']['verdict'] = 'invented'
        batches[3]['notes']['F001'] = 'not an object'
        for batch in batches:
            with self.assertRaises(HTTPError) as error: self.post(batch)
            self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.server.review_store.read()['revision'], 0)

    def test_private_routes_and_cross_origin_requests_are_rejected(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url.split('/')[0] + '//' + self.url.split('/')[2] + '/report.json')
        self.assertEqual(error.exception.code, 404)
        for headers in ({'Origin': 'https://example.com'}, {'Host': 'example.com'}):
            with self.assertRaises(HTTPError) as error: self.request(headers=headers)
            self.assertEqual(error.exception.code, 403)
        for path in ('../report.json', '%2e%2e/report.json', '.review-state.lock', 'other.txt'):
            with self.assertRaises(HTTPError) as error: self.request(path)
            self.assertEqual(error.exception.code, 404)

    def test_audio_ranges_for_seeking(self):
        with self.request('audio.wav', headers={'Range': 'bytes=2-5'}) as response:
            self.assertEqual(response.status, 206); self.assertEqual(response.read(), b'2345')
            self.assertEqual(response.headers['Content-Range'], 'bytes 2-5/10')
        with self.request('audio.wav', headers={'Range': 'bytes=-3'}) as response:
            self.assertEqual(response.read(), b'789')
        with self.assertRaises(HTTPError) as error: self.request('audio.wav', headers={'Range': 'bytes=99-'})
        self.assertEqual(error.exception.code, 416)

    def test_report_change_refuses_saved_state(self):
        self.report['script'] = 'changed'
        (self.root / 'report.json').write_text(json.dumps(self.report))
        with self.assertRaises(HTTPError) as error: self.request()
        self.assertEqual(error.exception.code, 409)
        with self.assertRaises(Conflict): ReviewStore(self.root)

    def test_import_existing_export_once_and_render_saved_notes(self):
        # Existing file export remains compatible; server state is authoritative afterwards.
        other = self.root / 'other'; other.mkdir()
        (other / 'report.json').write_bytes((self.root / 'report.json').read_bytes())
        batch = self.payload(); batch.pop('revision'); batch['exported_at'] = '2026-10-21T12:00:00Z'
        (other / 'listening-notes.json').write_text(json.dumps(batch))
        state = ReviewStore(other).read()
        self.assertEqual(state['notes']['F001']['heard'], 'しゅうたん')
        self.post(self.payload())
        with self.request('') as response: html = response.read().decode()
        self.assertIn('review-state.json', html); self.assertIn('api/complete', html)
        self.assertIn('しゅうたん', html)

    def test_symlink_audio_cannot_expose_other_file(self):
        secret = self.root.parent / (self.root.name + '-secret')
        secret.write_bytes(b'secret'); self.addCleanup(secret.unlink)
        (self.root / 'audio.wav').unlink(); (self.root / 'audio.wav').symlink_to(secret)
        with self.assertRaises(HTTPError) as error: self.request('audio.wav')
        self.assertEqual(error.exception.code, 404)

    def test_completion_with_uncertainty_is_not_approval(self):
        payload = self.payload(); payload['notes']['F001']['verdict'] = 'uncertain'
        state = self.post(payload, 'api/complete')
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['verdict_counts']['uncertain'], 1)
        self.assertEqual(state['unreviewed_count'], 1)
        self.assertIn('does not certify', state['scope'])

    def test_failed_atomic_replace_keeps_last_saved_state(self):
        before = (self.root / 'review-state.json').read_bytes()
        with patch('tts_audit.server.os.replace', side_effect=OSError('disk failure')):
            with self.assertRaises(HTTPError) as error: self.post(self.payload())
            self.assertEqual(error.exception.code, 500)
        self.assertEqual((self.root / 'review-state.json').read_bytes(), before)
        self.assertEqual(list(self.root.glob('.review-state-*')), [])
        self.assertEqual(self.post(self.payload())['revision'], 1)
