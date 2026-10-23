"""Validate optional, audio-derived display timing without changing ASR/reviews."""
import hashlib
import json
import math


def transcript_fingerprint(transcript):
    raw = json.dumps(transcript.get('segments', []), ensure_ascii=False,
                     sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def validate_audio_timing(report, transcript, timing):
    if not isinstance(timing, dict) or timing.get('schema_version') != 1:
        raise ValueError('Invalid audio timing schema')
    if timing.get('method') != 'kana_whisper_token_attention_dtw':
        raise ValueError('Unsupported audio timing method')
    if timing.get('run_id') != report.get('run_id'):
        raise ValueError('Timing belongs to another run')
    if not report.get('audio_sha256') or timing.get('audio_sha256') != report['audio_sha256']:
        raise ValueError('Timing belongs to different audio')
    if timing.get('transcript_sha256') != transcript_fingerprint(transcript):
        raise ValueError('Timing belongs to a different transcript')
    chars = timing.get('characters')
    text = ''.join(s['text'] for s in transcript.get('segments', []))
    if not isinstance(chars, list) or len(chars) != len(text):
        raise ValueError('Timing character count mismatch')
    previous = 0
    for i, (ch, value) in enumerate(zip(text, chars)):
        if not isinstance(value, dict) or value.get('text') != ch:
            raise ValueError('Timing text mismatch')
        a, b = value.get('start_s'), value.get('end_s')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (a, b)):
            raise ValueError('Invalid timing values')
        if not 0 <= a <= b <= report['duration_s']+.001 or a < previous-.001:
            raise ValueError('Timing is non-monotonic or outside the audio')
        previous = b
    return chars


def project_audio_timing(report, transcript, timing_segments):
    """Map audio-only DTW groups to the unchanged ASR text, marking interpolations."""
    from difflib import SequenceMatcher
    from .core import normalize
    segments = transcript['segments']
    if len(segments) != len(timing_segments):
        raise ValueError('Incomplete timing segments')
    characters, quality = [], []
    for segment, timed in zip(segments, timing_segments):
        new = []
        for group in timed['groups']:
            text = group['text']
            if not text: continue
            a = max(segment['start_s'], min(segment['end_s'], segment['start_s'] + group['start_s']))
            b = max(a, min(segment['end_s'], segment['start_s'] + group['end_s']))
            new.extend(dict(text=ch, start_s=a+(b-a)*j/len(text),
                            end_s=a+(b-a)*(j+1)/len(text),
                            source='attention_dtw' if len(text)==1 else 'within_token_interpolation')
                       for j,ch in enumerate(text))
        if ''.join(c['text'] for c in new) != timed['text']:
            raise ValueError('Incomplete timing text')
        old_norm, old_offsets = normalize(segment['text'])
        new_norm, new_offsets = normalize(timed['text'])
        mapped, equal = {}, 0
        for tag,a,b,c,d in SequenceMatcher(None,old_norm,new_norm,autojunk=False).get_opcodes():
            if tag != 'equal': continue
            equal += b-a
            for x,y in zip(range(a,b),range(c,d)):
                mapped[old_offsets[x]] = dict(new[new_offsets[y]], text=segment['text'][old_offsets[x]])
        coverage = equal/max(1,len(old_norm))
        if coverage < .85: raise ValueError('Insufficient matching kana for audio timing')
        local, j = [], 0
        while j < len(segment['text']):
            if j in mapped:
                local.append(mapped[j]); j+=1; continue
            k=j
            while k<len(segment['text']) and k not in mapped: k+=1
            a=local[-1]['end_s'] if local else segment['start_s']
            b=max(a,mapped[k]['start_s'] if k in mapped else segment['end_s'])
            local.extend(dict(text=segment['text'][v],start_s=a+(b-a)*(v-j)/(k-j),
                              end_s=a+(b-a)*(v-j+1)/(k-j),source='unmatched_or_punctuation_interpolation')
                         for v in range(j,k))
            j=k
        characters.extend(local)
        quality.append(dict(kana_match_fraction=coverage, timestamp_recognition_same_text=segment['text']==timed['text']))
    timing=dict(schema_version=1,method='kana_whisper_token_attention_dtw',run_id=report['run_id'],
                audio_sha256=report['audio_sha256'],transcript_sha256=transcript_fingerprint(transcript),
                characters=characters,segment_quality=quality,human_timestamps_verified=False)
    validate_audio_timing(report,transcript,timing)
    return timing
