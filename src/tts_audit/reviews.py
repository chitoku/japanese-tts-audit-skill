"""Validate and archive exported human reviews without changing ASR evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .report import render
from .reviews_time import timestamp
from .annotations import merge_annotations


def merge_notes(report, incoming, existing=None):
    if any(b is not None and not isinstance(b, dict) for b in (existing, incoming)):
        raise ValueError('Invalid review batch')
    annotations = merge_annotations(report, *((b or {}).get('annotations', []) for b in (existing, incoming)))
    valid_ids = {f['id'] for f in report['findings']} | {a['id'] for a in annotations if a['kind'] == 'manual_flag'}
    merged = {}
    for batch in (existing, incoming):
        if batch is None:
            continue
        if batch.get('schema_version') != 1 or batch.get('run_id') != report['run_id']:
            raise ValueError('Review schema or run_id does not match the report')
        timestamp(batch['exported_at'])
        if not isinstance(batch.get('notes'), dict):
            raise ValueError('notes must be an object')
        for ident, note in batch['notes'].items():
            if ident not in valid_ids:
                raise ValueError('Unknown finding ID: ' + ident)
            if note.get('verdict') not in {'correct', 'error', 'uncertain', 'dictionary', 'unreviewed'}:
                raise ValueError('Invalid verdict: ' + ident)
            if not all(isinstance(note.get(field), str) for field in ('heard', 'note', 'updated_at')):
                raise ValueError('Invalid review fields: ' + ident)
            for field in ('target_text','expected_reading','deleted'):
                if field in note:
                    if not ident.startswith('M-'):raise ValueError('Manual metadata requires a manual flag')
                    if field=='deleted':
                        if type(note[field]) is not bool:raise ValueError('Invalid manual deletion')
                    elif not isinstance(note[field],str) or len(note[field])>2000:raise ValueError('Invalid manual text')
            when = timestamp(note['updated_at'])
            if ident not in merged or when > timestamp(merged[ident]['updated_at']):
                merged[ident] = dict(note)
            elif when == timestamp(merged[ident]['updated_at']) and note != merged[ident]:
                raise ValueError('Conflicting reviews with the same timestamp: ' + ident)
    return {**({'annotations': annotations} if annotations else {}), 'schema_version': 1, 'run_id': report['run_id'],
            'exported_at': max((b['exported_at'] for b in (existing, incoming) if b), key=timestamp),
            'notes': merged}


def import_reviews(directory, source):
    directory, source = Path(directory), Path(source)
    raw = source.read_bytes()
    report = json.loads((directory / 'report.json').read_text())
    destination = directory / 'listening-notes.json'
    existing = json.loads(destination.read_text()) if destination.exists() else None
    merged = merge_notes(report, json.loads(raw), existing)
    counts = Counter(n['verdict'] for n in merged['notes'].values() if not n.get('deleted'))
    summary = {'run_id': report['run_id'], 'reviewed_count': sum(not n.get('deleted') for n in merged['notes'].values()),
               'verdict_counts': dict(counts),
               'annotations': merged.get('annotations', []),
               'manual_findings': [dict(a, human_review=merged['notes'].get(a['id']))
                                   for a in merged.get('annotations', []) if a['kind'] == 'manual_flag' and not merged['notes'].get(a['id'],{}).get('deleted')],
               'scope': 'Human labels on flagged candidates only; recall and overall model error rate are not measured.',
               'findings': [dict(f, human_review=merged['notes'][f['id']])
                            for f in report['findings'] if f['id'] in merged['notes']]}
    html = render(report, merged)
    archive = directory / 'review-imports'
    archive.mkdir(exist_ok=True)
    (archive / (hashlib.sha256(raw).hexdigest() + '.json')).write_bytes(raw)
    for name, value in [('listening-notes.json', merged), ('review-summary.json', summary)]:
        (directory / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (directory / 'report.html').write_text(html, encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report_directory')
    parser.add_argument('exported_notes')
    args = parser.parse_args()
    result = import_reviews(args.report_directory, args.exported_notes)
    print(json.dumps({'reviewed_count': result['reviewed_count'], 'verdict_counts': result['verdict_counts']}))
