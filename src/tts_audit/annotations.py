"""Human-added time ranges, separate from immutable machine findings."""
import math
import re
from .reviews_time import timestamp


def merge_annotations(report, *batches):
    merged = {}
    for batch in batches:
        if not isinstance(batch, list) or len(batch) > 5000:
            raise ValueError('Invalid annotations')
        for item in batch:
            if not isinstance(item, dict):
                raise ValueError('Invalid annotation')
            ident, kind = item.get('id'), item.get('kind')
            if kind not in {'manual_flag', 'reviewed_range'} or not isinstance(ident, str):
                raise ValueError('Invalid annotation kind or ID')
            prefix = 'M-' if kind == 'manual_flag' else 'S-'
            if not re.fullmatch(re.escape(prefix) + r'[A-Za-z0-9-]{1,90}', ident):
                raise ValueError('Invalid annotation ID')
            start, end = item.get('start_s'), item.get('end_s')
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in (start, end)):
                raise ValueError('Invalid annotation range')
            if not 0 <= start < end <= report['duration_s']:
                raise ValueError('Annotation is outside the audio')
            timestamp(item.get('created_at'))
            clean = {key: item[key] for key in ('id', 'kind', 'start_s', 'end_s', 'created_at')}
            if ident in merged and merged[ident] != clean:
                raise ValueError('Conflicting annotation ID')
            merged[ident] = clean
    if len(merged) > 5000:
        raise ValueError('Too many annotations')
    return list(merged.values())
