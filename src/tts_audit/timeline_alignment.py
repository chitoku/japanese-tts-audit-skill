"""Text-to-text projection for review display, never forced audio alignment."""
from difflib import SequenceMatcher
from .core import normalize
from .audio_timing import validate_audio_timing


def build_timeline_alignment(report, transcript, timing=None):
    segments = transcript.get('segments', [])
    duration = report.get('duration_s', 0)
    actual, positions, chars = '', [], []
    for si, segment in enumerate(segments):
        text = segment.get('text', '')
        start, end = segment['start_s'], segment['end_s']
        base = len(chars)
        n = max(1, len(text))
        chars.extend({'text': ch, 'start_s': start+(end-start)*i/n,
                      'end_s': start+(end-start)*(i+1)/n, 'segment': si,
                      'finding_ids': []} for i, ch in enumerate(text))
        norm, offsets = normalize(text)
        actual += norm
        positions.extend(base+i for i in offsets)
    timing_status = 'absent'
    if timing is not None:
        try:
            timed_chars = validate_audio_timing(report, transcript, timing)
            for char, timed in zip(chars, timed_chars):
                char.update(start_s=timed['start_s'], end_s=timed['end_s'], timing_source=timed.get('source', 'attention_dtw'))
            timing_status = 'accepted'
        except (ValueError, TypeError, KeyError):
            timing_status = 'rejected'
    units, expected = [], ''
    for item in report.get('reading_units', []):
        norm, _ = normalize(item.get('reading', ''))
        units.append(dict(item, normalized_start=len(expected), normalized_end=len(expected)+len(norm)))
        expected += norm
    opcodes = SequenceMatcher(None, expected, actual, autojunk=False).get_opcodes()

    def project(pos, end=False):
        for tag, a, b, c, d in opcodes:
            if (a < pos <= b if end else a <= pos < b):
                if tag == 'equal': return c+pos-a
                if b > a: return c+(d-c)*(pos-a)/(b-a)
                return d if end else c
        return len(actual) if pos >= len(expected) else 0

    def at(pos, end=False):
        if not chars or not positions: return duration * pos/max(1, len(actual))
        if end and pos > 0 and abs(pos-round(pos)) < .000001:
            return chars[positions[min(len(positions)-1, int(pos)-1)]]['end_s']
        if pos >= len(positions): return chars[positions[-1]]['end_s']
        lo = max(0, min(len(positions)-1, int(pos)))
        ch = chars[positions[lo]]
        return ch['start_s']+(ch['end_s']-ch['start_s'])*(pos-lo)

    findings = {}
    for f in report.get('findings', []):
        touched = [u for u in units if u['start'] < f.get('script_end', -1) and u['end'] > f.get('script_start', -1)]
        if not touched: continue
        j0 = max(0, int(project(touched[0]['normalized_start'])))
        j1 = min(len(actual), int(project(touched[-1]['normalized_end'], True)+.00001))
        # Keep the original finding's full observed text (including extra syllables).
        # Match only near the projected occurrence, with context resolving repeats.
        needle, _ = normalize(f.get('observed_kana', ''))
        if needle:
            lo, hi = max(0, j0-max(12, len(needle)*2)), min(len(actual), j1+max(12, len(needle)*2))
            matches, cursor = [], lo
            while cursor <= hi-len(needle):
                match = actual.find(needle, cursor, hi)
                if match < 0: break
                matches.append(match)
                cursor = match+1
            if matches:
                match = min(matches, key=lambda x: abs(x-j0)+abs(x+len(needle)-j1))
                j0, j1 = match, match+len(needle)
        # Highlight a specific occurrence, never a global substring search for e.g. ニ.
        offsets = positions[j0:j1]
        for offset in offsets:
            if f['id'] not in chars[offset]['finding_ids']:
                chars[offset]['finding_ids'].append(f['id'])
        start, end = at(j0), at(max(j0, j1), True)
        findings[f['id']] = {'start_s': start, 'end_s': max(start, end),
                             'focus_s': (start+max(start, end))/2,
                             'observed_start': offsets[0] if offsets else None,
                             'observed_end': offsets[-1]+1 if offsets else None,
                             'method': 'audio_derived_text_projection' if timing_status == 'accepted' else 'text_projection_within_asr_segment'}
    script_tokens = []
    for u in units:
        a, b = u['normalized_start'], u['normalized_end']
        start, end = at(project(a)), at(project(b, True), True)
        ids = [f['id'] for f in report.get('findings', [])
               if u['start'] < f.get('script_end', -1) and u['end'] > f.get('script_start', -1)]
        script_tokens.append({'text': report.get('script', '')[u['start']:u['end']],
                              'script_start': u['start'], 'script_end': u['end'],
                              'start_s': start, 'end_s': max(start, end), 'finding_ids': ids})
    return {'method': 'kana_whisper_token_attention_dtw' if timing_status == 'accepted' else 'text_projection_within_asr_segment',
            'timing_status': timing_status,
            'word_timestamps_verified': False, 'pixels_per_second': 120,
            'script_tokens': script_tokens, 'kana_chars': chars, 'findings': findings,
            'warning': ('Kana Whisperの音声注意・DTWによる時刻推定。トークン内は按分。人の時刻確認は未実施です。' if timing_status == 'accepted' else ('時刻データの不一致のため概算表示。' if timing_status == 'rejected' else '')+'台本とASRの文字列照合を認識区間内に按分した位置目安です。音声との強制アラインメントではありません。')}
