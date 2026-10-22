"""Validate, export and score the frozen, span-labeled development benchmark.

Standard library only; never calls TTS or ASR services.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1] / 'data/benchmark'
SCORED = {'reviewed_error', 'reviewed_correct'}
STATUSES = SCORED | {'needs_adjudication', 'reported_lead', 'excluded_variant'}

def load_lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def unique(rows):
    result = {r['id']: r for r in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate IDs')
    return result

def load(root=ROOT, version='v0.1.0'):
    frozen = root / 'versions' / version
    manifest = json.loads((frozen / 'manifest.json').read_text())
    return manifest, unique(load_lines(frozen / 'observations.jsonl')), unique(load_lines(frozen / 'prompts.jsonl'))

def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path outside benchmark: ' + relative)
    return path

def validate(root=ROOT, version='v0.1.0'):
    manifest, obs, prompts = load(root, version)
    for relative, entry in manifest['files'].items():
        data = safe_path(root, relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256'] or len(data) != entry['bytes']:
            raise ValueError('Frozen file changed: ' + relative)
    if manifest['dataset_version'] != version:
        raise ValueError('Dataset version mismatch')
    actual = {r['id'] for r in obs.values() if r['status'] in SCORED}
    if actual != set(manifest['scored_observation_ids']) or len(actual) != len(manifest['scored_observation_ids']):
        raise ValueError('Scored membership mismatch')
    if len(obs) != manifest['counts']['observations'] or len(prompts) != manifest['counts']['prompts']:
        raise ValueError('Count mismatch')
    if dict(collections.Counter(r['status'] for r in obs.values())) != manifest['counts']['statuses']:
        raise ValueError('Status count mismatch')
    terms = unique(load_lines(root / 'versions' / version / 'terms.jsonl'))
    if len(terms) != manifest['counts']['terms']:
        raise ValueError('Term count mismatch')
    for prompt in prompts.values():
        a, b = prompt['script_span']
        if not (0 <= a < b <= len(prompt['text'])) or prompt['text'][a:b] != prompt['surface']:
            raise ValueError('Invalid script span: ' + prompt['id'])
        for oid in prompt['observation_ids']:
            if oid not in obs or obs[oid]['prompt_id'] != prompt['id']:
                raise ValueError('Broken observation link')
    for row in obs.values():
        if row['status'] not in STATUSES or row['term_id'] not in terms:
            raise ValueError('Invalid status or term: ' + row['id'])
        pid = row['prompt_id']
        if pid is not None and (pid not in prompts or row['id'] not in prompts[pid]['observation_ids']):
            raise ValueError('Broken prompt link')
        if row['audio']:
            asset = row['audio']
            if manifest['files'].get(asset['path'], {}).get('sha256') != asset['sha256']:
                raise ValueError('Audio fingerprint not pinned')
        if row['status'] in SCORED:
            if not row['audio'] or not pid or not row['human_review'] or row['reviewer_count'] < 1:
                raise ValueError('Scored observation lacks audio, script or human evidence')
            if row['status'] == 'reviewed_error' and not row['human_heard']:
                raise ValueError('Positive observation lacks human transcription')
    return manifest['counts']

def export(out, root=ROOT, version='v0.1.0'):
    validate(root, version)
    _, obs, prompts = load(root, version)
    if out.exists():
        raise ValueError('Export directory already exists; avoid overwriting a run')
    out.mkdir(parents=True)
    jobs = []
    for row in obs.values():
        if row['status'] not in SCORED:
            continue
        prompt = prompts[row['prompt_id']]
        case = out / row['id']
        case.mkdir()
        suffix = Path(row['audio']['path']).suffix
        shutil.copyfile(root / row['audio']['path'], case / ('audio' + suffix))
        (case / 'script.txt').write_text(prompt['text'] + '\n', encoding='utf-8')
        # Reference readings belong in text comparison, never in ASR decoding prompts.
        (case / 'readings.json').write_text(json.dumps({row['surface']: row['expected_kana']}, ensure_ascii=False) + '\n', encoding='utf-8')
        jobs.append({'id': row['id'], 'audio_sha256': row['audio']['sha256'],
            'audio': row['id'] + '/audio' + suffix, 'script': row['id'] + '/script.txt',
            'readings': row['id'] + '/readings.json'})
    (out / 'jobs.jsonl').write_text(''.join(json.dumps(j, ensure_ascii=False) + '\n' for j in jobs), encoding='utf-8')
    return {'exported_jobs': len(jobs)}

def score(predictions, root=ROOT, version='v0.1.0'):
    validate(root, version)
    manifest, obs, prompts = load(root, version)
    predicted = unique(predictions)
    if set(predicted) != set(manifest['scored_observation_ids']):
        raise ValueError('Predictions must cover exactly the scored IDs; missing cases cannot disappear')
    counts = collections.Counter({'tp': 0, 'fn': 0, 'fp': 0, 'tn': 0})
    for oid, prediction in predicted.items():
        row = obs[oid]
        if prediction.get('audio_sha256') != row['audio']['sha256']:
            raise ValueError('Prediction uses different audio: ' + oid)
        prompt = prompts[row['prompt_id']]
        a, b = prompt['script_span']
        hit = False
        for finding in prediction['findings']:
            start, end = finding['script_start'], finding['script_end']
            if type(start) is not int or type(end) is not int or not (0 <= start < end <= len(prompt['text'])):
                raise ValueError('Invalid prediction span: ' + oid)
            hit |= start < b and end > a
        positive = row['status'] == 'reviewed_error'
        counts['tp' if hit and positive else 'fp' if hit else 'fn' if positive else 'tn'] += 1
    def ratio(n, d):
        return n / d if d else None
    return {'dataset_version': version, 'scope': 'annotated word occurrences only; other regions are unscored',
        'split': 'development; not held out', **counts,
        'precision': ratio(counts['tp'], counts['tp'] + counts['fp']),
        'recall': ratio(counts['tp'], counts['tp'] + counts['fn']),
        'false_positive_rate': ratio(counts['fp'], counts['fp'] + counts['tn'])}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    current = json.loads((ROOT / 'current.json').read_text())['dataset_version']
    ap.add_argument('--version', default=current)
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('validate')
    export_ap = sub.add_parser('export')
    export_ap.add_argument('--out', required=True, type=Path)
    score_ap = sub.add_parser('score')
    score_ap.add_argument('predictions', type=Path)
    args = ap.parse_args()
    try:
        if args.command == 'validate':
            result = validate(version=args.version)
        elif args.command == 'export':
            result = export(args.out, version=args.version)
        else:
            result = score(load_lines(args.predictions), version=args.version)
    except (ValueError, KeyError, OSError) as error:
        ap.exit(1, str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
