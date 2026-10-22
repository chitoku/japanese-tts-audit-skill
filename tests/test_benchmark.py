"""Integrity and scoring contracts for the fixed, human-labeled benchmark."""
import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import benchmark


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.observations, cls.prompts = benchmark.load()

    def predictions(self, flag_errors=False):
        result = []
        for oid in self.manifest['scored_observation_ids']:
            row = self.observations[oid]
            prompt = self.prompts[row['prompt_id']]
            a, b = prompt['script_span']
            result.append({'id': oid, 'audio_sha256': row['audio']['sha256'],
                'findings': [{'script_start': a, 'script_end': b}] if flag_errors and row['status'] == 'reviewed_error' else []})
        return result

    def test_pinned_assets_and_evidence_are_complete(self):
        counts = benchmark.validate()
        self.assertEqual(counts['statuses']['reviewed_error'], 32)
        self.assertEqual(counts['statuses']['reviewed_correct'], 9)
        scored = set(self.manifest['scored_observation_ids'])
        for row in self.observations.values():
            if row['status'] in {'reported_lead', 'excluded_variant', 'needs_adjudication'}:
                self.assertNotIn(row['id'], scored)
        # Off-target human notes survive without rewriting the original button.
        off_target = next(r for r in self.observations.values() if r['source_id'] == 'history-supplement:H0165')
        self.assertEqual(off_target['human_review']['verdict'], 'correct')
        self.assertEqual(off_target['human_heard'], 'ベー')
        self.assertEqual(off_target['status'], 'needs_adjudication')

    def test_scoring_retains_false_negatives_and_negative_controls(self):
        empty = benchmark.score(self.predictions())
        self.assertEqual((empty['tp'], empty['fn'], empty['fp'], empty['tn']), (0, 32, 0, 9))
        oracle = benchmark.score(self.predictions(True))
        self.assertEqual((oracle['tp'], oracle['fn'], oracle['fp'], oracle['tn']), (32, 0, 0, 9))
        # Flagging everything must incur false alarms rather than perfect precision.
        all_flagged = self.predictions()
        for pred in all_flagged:
            text = self.prompts[self.observations[pred['id']]['prompt_id']]['text']
            pred['findings'] = [{'script_start': 0, 'script_end': len(text)}]
        result = benchmark.score(all_flagged)
        self.assertEqual(result['false_positive_rate'], 1)
        self.assertLess(result['precision'], 1)

    def test_missing_duplicate_or_different_audio_cannot_be_scored(self):
        predictions = self.predictions()
        with self.assertRaises(ValueError):
            benchmark.score(predictions[:-1])
        with self.assertRaises(ValueError):
            benchmark.score(predictions + [predictions[0]])
        different = copy.deepcopy(predictions)
        different[0]['audio_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            benchmark.score(different)

    def test_only_annotated_word_counts_as_detection(self):
        predictions = self.predictions()
        positive = next(p for p in predictions if self.observations[p['id']]['status'] == 'reviewed_error'
            and self.prompts[self.observations[p['id']]['prompt_id']]['script_span'][0] > 0)
        positive['findings'] = [{'script_start': 0, 'script_end': 1}]
        self.assertEqual(benchmark.score(predictions)['tp'], 0)
        positive['findings'] = [{'script_start': -1, 'script_end': 1}]
        with self.assertRaises(ValueError):
            benchmark.score(predictions)

    def test_export_contains_inputs_without_human_answer_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'run'
            result = benchmark.export(out)
            self.assertEqual(result['exported_jobs'], 41)
            for job in benchmark.load_lines(out / 'jobs.jsonl'):
                self.assertNotIn('human_heard', job)
                self.assertNotIn('status', job)
                self.assertTrue((out / job['audio']).is_file())
            with self.assertRaises(ValueError):
                benchmark.export(out)

    def test_modified_audio_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'benchmark'
            shutil.copytree(benchmark.ROOT, root)
            asset = next(r['audio']['path'] for r in self.observations.values() if r['audio'])
            (root / asset).write_bytes(b'changed audio')
            with self.assertRaisesRegex(ValueError, 'Frozen file changed'):
                benchmark.validate(root)


if __name__ == '__main__':
    unittest.main()
