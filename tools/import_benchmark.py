"""One-time migration of local research into a portable, frozen development benchmark.

No synthesis, recognition or network access. Run against the original outputs directory.
Never rerun over a published dataset version: create a new version for amendments.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil

VERSION = 'v0.1.0'
REPO = Path(__file__).resolve().parents[1]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def stable(prefix, *parts):
    return prefix + digest('\0'.join(parts).encode())[:16]

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def jsonl(path, values):
    path.write_text(''.join(json.dumps(v, ensure_ascii=False, sort_keys=True) + '\n' for v in values), encoding='utf-8')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--outputs', type=Path, required=True)
    args = ap.parse_args()
    root = args.outputs.resolve()
    dest = REPO / 'data/benchmark'
    frozen = dest / 'versions' / VERSION
    if (frozen / 'manifest.json').exists():
        raise SystemExit('Version already exists. Do not overwrite: introduce a new version.')
    frozen.mkdir(parents=True, exist_ok=True)
    provenance = dest / 'provenance' / VERSION
    observations, prompts, assets, source_files = {}, {}, {}, {}
    policy = json.loads((REPO / 'research/2026-10-21/reading-review-policy.json').read_text())
    excluded = set(policy['excluded_targets_for_new_corpora'])

    def read(relative):
        path = root / relative
        raw = path.read_bytes()
        source_files[relative] = {'sha256': digest(raw), 'bytes': len(raw)}
        return json.loads(raw)

    def add_prompt(text, surface, expected, readings=None, reading_source=None):
        if not text or not surface or surface not in text:
            return None
        # Span identity must be unambiguous; repeated occurrences require manual annotation.
        if text.count(surface) != 1:
            return None
        pid = stable('P-', text, surface, expected)
        prompts.setdefault(pid, {'id': pid, 'text': text, 'surface': surface,
            'script_span': [text.index(surface), text.index(surface) + len(surface)],
            'expected_kana': expected, 'accepted_readings': readings or [expected],
            'reading_source': reading_source, 'reading_review': 'imported_reference_not_independently_revalidated',
            'generation_eligible': surface not in excluded,
            'stage': 'candidate_prompt_not_gold',
            'exclusion_reason': 'user_excluded_variant_or_context_debate' if surface in excluded else None,
            'observation_ids': []})
        return pid

    def audio(relative):
        path = root / relative
        data = path.read_bytes()
        sha = digest(data)
        rel = 'audio/' + sha + path.suffix.lower()
        target = dest / rel
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            shutil.copyfile(path, target)
        assets[rel] = {'sha256': sha, 'bytes': len(data)}
        return {'path': rel, 'sha256': sha, 'timing': 'whole_clip; no independently aligned target timestamps'}

    def add(source_id, surface, expected, heard, text='', provider=None, model=None,
            status='needs_adjudication', phenomenon='unclassified', review=None,
            audio_path=None, source_path=None, source_row=None, reading_source=None,
            recognition=None, url=None, location=None, reason=None, readings=None):
        oid = stable('O-', source_id, surface)
        pid = add_prompt(text, surface, expected, readings, reading_source)
        # Missing or ambiguous script spans never become scored cases.
        if status.startswith('reviewed_') and not pid:
            status = 'needs_adjudication'
            reason = 'Missing unambiguous script span; original label retained.'
        if surface in excluded:
            status = 'excluded_variant'
        obs = {'id': oid, 'source_id': source_id, 'term_id': stable('T-', surface),
            'surface': surface, 'prompt_id': pid, 'expected_kana': expected,
            'human_heard': heard, 'provider': provider, 'model_label': model,
            'status': status, 'phenomenon': phenomenon,
            'human_review': review, 'reviewer_count': 1 if review else 0,
            'label_scope': 'specified script span only; not whole-clip certification',
            'audio': audio(audio_path) if audio_path else None,
            'recognition': recognition,
            'provenance': {'source_path': source_path, 'source_row': source_row,
                'url': url, 'location': location, 'assistant_audio_verified': False},
            'adjudication_note': reason}
        observations[oid] = obs
        if pid and oid not in prompts[pid]['observation_ids']:
            prompts[pid]['observation_ids'].append(oid)
        return obs

    records = {r['id']: r for r in read('evaluation-set-2026-10-21/recordings.json')}
    trial = {r['id']: r for r in read('voicevox-trial-2026-10-21/results.json')}
    script_path = 'tts-benchmark/sentences.v1.jsonl'
    raw = (root / script_path).read_bytes()
    source_files[script_path] = {'sha256': digest(raw), 'bytes': len(raw)}
    scripts = {r['id']: r for r in map(json.loads, raw.decode().splitlines())}
    for row in scripts.values():
        add_prompt(row['text'], row['target'], row['expected_kana'])
    errors = read('evaluation-set-2026-10-21/error-cases.json')
    for row in errors:
        if row['provider'] != 'ElevenLabs':
            continue  # VOICEVOX observations below retain both errors and controls.
        rec = records[row['id']]
        sentence = scripts[rec['sentence_id']]
        add(row['id'], row['surface'], row['expected_kana'], row['human_heard'],
            sentence['text'], row['provider'], rec['model_label'], 'reviewed_error',
            row['phenomenon'], review={'verdict': 'error', 'heard': row['human_heard'], 'reason': row['reason']},
            audio_path=row['audio'], source_path='evaluation-set-2026-10-21/error-cases.json',
            source_row=row, recognition=rec.get('existing_recognition'))
    for row in read('evaluation-set-2026-10-21/voicevox-spans.json'):
        rec = records[row['recording_id']]
        cls = row['curated_class']
        status = {'human_supported_error': 'reviewed_error', 'asr_false_alarm': 'reviewed_correct'}.get(cls, 'needs_adjudication')
        if cls in {'accepted_reading', 'equivalent_notation', 'natural_pronunciation', 'expected_reading_issue'}:
            status = 'excluded_variant'
        add('voicevox:' + row['id'], row['surface'], row['expected_kana'], row['human_heard'],
            rec['text'], rec['provider'], rec['model_label'], status, row['phenomenon'],
            review={k: row[k] for k in ['original_verdict', 'original_note', 'human_heard', 'curated_class', 'reason']},
            audio_path=rec['audio'], source_path='evaluation-set-2026-10-21/voicevox-spans.json',
            # Original start/end are concatenated-batch offsets, not sample timestamps.
            source_row=row, recognition={'kana_whisper': trial[rec['sentence_id']]['kana_asr']}, reason=row['reason'])

    comparison = {r['id']: r for r in read('tts-provider-comparison-2026-10-21/comparison-index.json')}
    for row in comparison.values():
        add_prompt(row['text'], row['target'], row['expected_kana'])
    summary = read('tts-provider-comparison-2026-10-21/human-confirmed-nonlexical-summary.json')
    for row in summary['core_nonlexical'] + summary['adjacent_phonetic_errors']:
        if not row['provider'].startswith('Google'):
            continue  # Already represented by the earlier VOICEVOX recording.
        rec = comparison[row['id']]
        add('google-neural2:' + row['id'], row['surface'], row['expected'], row['heard'],
            rec['text'], 'Google', 'ja-JP-Neural2-C', 'reviewed_error',
            'abnormal_pronunciation_candidate' if row in summary['core_nonlexical'] else 'phonetic_change',
            review=row['review'], audio_path='google-neural2-1000-2026-10-21/samples/' + row['id'] + '/audio.wav',
            source_path='tts-provider-comparison-2026-10-21/human-confirmed-nonlexical-summary.json',
            source_row=row, reading_source=summary['sources'].get(row['surface']),
            recognition={'kana_whisper': rec['google']['kana']})

    history = {r['id']: r for r in read('voicevox-history-200-2026-10-21/review-index.json')}
    state = read('voicevox-history-200-2026-10-21/review-state.json')
    for row in history.values():
        add_prompt(row['text'], row['target'], row['expected_kana'], row['accepted_readings'], row.get('reading_source'))
    for sid, note in state['notes'].items():
        if note['verdict'] == 'correct' and sid not in {'H0107', 'H0165'}:
            continue  # Whole-sentence correct buttons do not certify individual phonemes.
        row = history[sid]
        status = 'reviewed_error' if sid in {'H0007', 'H0018', 'H0059', 'H0171'} else 'needs_adjudication'
        add('history:' + sid, row['target'], row['expected_kana'], note['heard'],
            row['text'], 'VOICEVOX', '青山龍星・ノーマル／Engine 0.25.2', status,
            'omission' if sid == 'H0059' else 'reading_error_candidate', review=note,
            audio_path='voicevox-history-200-2026-10-21/samples/' + sid + '/audio.wav',
            source_path='voicevox-history-200-2026-10-21/review-state.json', source_row={'id': sid, **note},
            readings=row['accepted_readings'], reading_source=row.get('reading_source'),
            recognition={'kana_whisper': row['asr']},
            reason='Variant, ambiguous hearing or conflicting/missing judgment needs adjudication.' if status == 'needs_adjudication' else None)
    # These off-target observations must survive even though the original button says correct.
    for sid, surface, expected, heard in [('H0107', '捕り物', 'とりもの', 'トリブツ'), ('H0165', '米', 'こめ', 'ベー')]:
        row, note = history[sid], state['notes'][sid]
        add('history-supplement:' + sid, surface, expected, heard, row['text'], 'VOICEVOX',
            '青山龍星・ノーマル／Engine 0.25.2', 'needs_adjudication', 'off_target_reading',
            review=note, audio_path='voicevox-history-200-2026-10-21/samples/' + sid + '/audio.wav',
            source_path='voicevox-history-200-2026-10-21/review-state.json', source_row={'id': sid, **note},
            recognition={'kana_whisper': row['asr']},
            reason='Explicit user error note conflicts with correct button. Retain both; request span-specific adjudication.')

    # Import curated YouTube leads; deduplicate reports of the same video/word/hearing.
    leads = {}
    for path in sorted(root.glob('*/candidate_cases.jsonl')):
        rel = str(path.relative_to(root))
        raw = path.read_bytes()
        source_files[rel] = {'sha256': digest(raw), 'bytes': len(raw)}
        for row in map(json.loads, raw.decode().splitlines()):
            comment = row.get('source_comment') or {}
            url = row.get('video_url') or row.get('play_url') or comment.get('url') or ''
            video = row.get('video_id') or comment.get('video_id') or url
            word, heard = row.get('written_word', ''), row.get('reported_reading', '')
            key = (video, word, heard)
            if key not in leads:
                leads[key] = {'row': row, 'origins': []}
            leads[key]['origins'].append({'source_path': rel, 'case_id': row.get('case_id'),
                'comment_url': comment.get('url'), 'location': row.get('location') or row.get('locations') or row.get('location_seconds')})
    for (video, word, heard), item in sorted(leads.items()):
        row = item['row']
        add('youtube:' + video + ':' + heard, word, row.get('expected_reading', ''), heard,
            status='reported_lead', phenomenon='reported_reading_candidate', source_path=item['origins'][0]['source_path'],
            source_row={'case_ids': item['origins'], 'dictionary_source': row.get('dictionary_source') or row.get('dictionary_url'),
                'note': row.get('note') or row.get('dictionary_note')},
            url=row.get('play_url') or row.get('video_url') or (row.get('source_comment') or {}).get('url'),
            location=row.get('location') or row.get('locations') or row.get('location_seconds'),
            reason='Comment/caption location is a lead, not an independently verified timed audio label.')
    for rel in ['observed-cases/gVGsJntCY8A-user-report.json', 'observed-cases/iiOtK2qYE94-user-report.json']:
        report = read(rel)
        for row in report['entries']:
            add('youtube-user:' + report['video_id'], row['target'], row.get('reference_reading', ''), row['user_heard'],
                status='reported_lead', phenomenon=row['classification'],
                review={'source': 'user direct listening report', 'heard': row['user_heard']},
                source_path=rel, source_row={k: row[k] for k in ['note', 'reading_reference'] if k in row},
                url=report.get('url'), location={'seconds': row.get('timestamp_s'), 'status': row.get('timestamp_status')},
                reason='Audio not bundled; original script and exact spoken occurrence need confirmation.')

    # A motivating user example is a collection lead, not invented audio evidence.
    add('user-motivating-example:senritsu', '戦慄', 'せんりつ', 'せんぞう',
        status='reported_lead', phenomenon='abnormal_pronunciation_candidate',
        review={'source': 'user motivating example in this chat', 'heard': 'せんぞう'},
        source_path='conversation-history',
        reason='Original audio, script, provider and URL have not been recovered.')
    extra = json.loads((REPO / 'research/2026-10-21/additional-targets.json').read_text())
    for row in extra['targets']:
        for text in row['examples']:
            surface = next(w for w in row['spellings'] if w in text)
            add_prompt(text, surface, row['expected_kana'])
    obs = sorted(observations.values(), key=lambda r: r['id'])
    prompt_rows = sorted(prompts.values(), key=lambda r: r['id'])
    for row in prompt_rows:
        row['observation_ids'].sort()
        if any(observations[oid]['status'] in {'reviewed_error', 'reviewed_correct'} for oid in row['observation_ids']):
            row['stage'] = 'reviewed_observation_context'
    jsonl(frozen / 'observations.jsonl', obs)
    jsonl(frozen / 'prompts.jsonl', prompt_rows)
    # Selected source rows are retained in each observation; source inventory pins original files.
    dump(provenance / 'source-files.json', source_files)
    dump(provenance / 'import-policy.json', {'importer': 'tools/import_benchmark.py',
        'excluded_targets': sorted(excluded), 'source_root_convention': 'paths relative to original outputs/',
        'human_reviewers': 'single user; imported judgments, no new independent listening',
        'missing_collection': 'Uncurated comments and production demos are not yet canonicalized. Imported prompt references still require quality review.'})
    terms = []
    for word in sorted({r['surface'] for r in obs} | {r['surface'] for r in prompt_rows}):
        rows = [r for r in obs if r['surface'] == word]
        terms.append({'id': stable('T-', word), 'surface': word,
            'observation_ids': [r['id'] for r in rows],
            'prompt_ids': sorted(p['id'] for p in prompt_rows if p['surface'] == word),
            'aliases': ['捕物', '捕り物'] if word in {'捕物', '捕り物'} else [],
            'reviewed_error_count': sum(r['status'] == 'reviewed_error' for r in rows),
            'reported_readings': sorted({r['human_heard'] for r in rows if r['human_heard']})})
    jsonl(frozen / 'terms.jsonl', terms)
    dump(dest / 'current.json', {'dataset_version': VERSION, 'manifest': 'versions/' + VERSION + '/manifest.json'})
    core = [r['id'] for r in obs if r['status'] in {'reviewed_error', 'reviewed_correct'}]
    files = {}
    for path in [frozen / 'observations.jsonl', frozen / 'prompts.jsonl', frozen / 'terms.jsonl', *sorted(provenance.glob('*.json'))]:
        files[str(path.relative_to(dest))] = {'sha256': digest(path.read_bytes()), 'bytes': path.stat().st_size}
    files.update(assets)
    dump(frozen / 'manifest.json', {'schema_version': '1', 'dataset_version': VERSION,
        'purpose': 'Development/regression benchmark; no independent held-out population accuracy claims',
        'count_unit': 'observation = audio + specified word occurrence, not unique word or whole clean recording',
        'counts': {'observations': len(obs), 'terms': len(terms), 'prompts': len(prompts),
            'generation_eligible_prompts': sum(p['generation_eligible'] for p in prompt_rows),
            'statuses': dict(collections.Counter(r['status'] for r in obs)),
            'audio_files': len(assets), 'audio_bytes': sum(a['bytes'] for a in assets.values())},
        'scored_observation_ids': core, 'files': files,
        'labels': {'positive': 'reviewed_error', 'negative': 'reviewed_correct',
            'unscored': ['needs_adjudication', 'reported_lead', 'excluded_variant']},
        'audio_rights': 'Provider-generated research samples; separate from MIT code license. No YouTube audio copied.'})
    lines = ['# 誤読観測語集 — v0.1.0', '',
        '正本は `versions/v0.1.0/observations.jsonl`。同じ語の繰り返し生成は別観測。数字は箇所数で、語数ではありません。', '',
        '聴取済み誤読は単独聴取者のラベルです。未確定・YouTube報告は別枠で、採点に入りません。', '',
        '|語|期待読み|観測・報告された読み|提供元|状態|観測ID|音声・出典|', '|---|---|---|---|---|---|---|']
    labels = {'reviewed_error': '聴取済み誤読', 'reviewed_correct': '誤警報対照', 'needs_adjudication': '要裁定', 'reported_lead': '収集報告・未採用', 'excluded_variant': '別読み等・対象外'}
    for row in sorted(obs, key=lambda r: (r['surface'], r['status'], r['source_id'])):
        def cell(v):
            return str(v or '—').replace('|', '\\|').replace('\n', ' ')
        link = '[音声](' + row['audio']['path'] + ')' if row['audio'] else ('[出典](' + row['provenance']['url'] + ')' if row['provenance']['url'] else '出典未回収')
        lines.append('|'+ '|'.join(map(cell, [row['surface'], row['expected_kana'], row['human_heard'], row['provider'] or 'YouTube・提供元不明', labels[row['status']], row['id'], link]))+'|')
    (dest / 'WORDLIST.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'version': VERSION, **json.loads((frozen / 'manifest.json').read_text())['counts']}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
