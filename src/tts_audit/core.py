"""Dictionary readings and review-candidate alignment; not a pronunciation judge."""
import re
from difflib import SequenceMatcher

VOWELS = {}
for vowel, chars in [('ア','アカガサザタダナハバパマヤラワァ'),('イ','イキギシジチヂニヒビピミリィ'),('ウ','ウクグスズツヅヌフブプムユルヴゥュ'),('エ','エケゲセゼテデネヘベペメレェ'),('オ','オコゴソゾトドノホボポモヨロヲォョ')]:
    for ch in chars: VOWELS[ch] = vowel
VOWELS['ャ'] = 'ア'

def normalize(text):
    """Return kana plus source-character offsets; treat common long-vowel spellings alike."""
    chars, offsets = [], []
    for i, ch in enumerate(text):
        if 'ぁ' <= ch <= 'ゖ': ch = chr(ord(ch) + 0x60)
        if ch == 'ヲ': ch = 'オ'
        if ch == 'ー':
            ch = VOWELS.get(chars[-1], '') if chars else ''
        if not ('ァ' <= ch <= 'ヺ'): continue
        if chars and ((ch == 'ウ' and VOWELS.get(chars[-1]) == 'オ') or (ch == 'イ' and VOWELS.get(chars[-1]) == 'エ')):
            ch = VOWELS[chars[-1]]
        chars.append(ch); offsets.append(i)
    return ''.join(chars), offsets

def expected_readings(text, overrides=None):
    from sudachipy import dictionary, tokenizer
    tok = dictionary.Dictionary().tokenizer()
    overrides = overrides or {}
    if any(not isinstance(k,str) or not k or not isinstance(v,str) or not v for k,v in overrides.items()):
        raise ValueError('readings JSON must map nonempty original strings to nonempty readings')
    pattern = re.compile('|'.join(map(re.escape, sorted(overrides, key=len, reverse=True)))) if overrides else None
    units, warnings = [], []
    def add(surface, reading, start, source):
        if not surface.strip(): return
        normalized, _ = normalize(reading)
        unsupported = re.sub(r'[ぁ-ゖァ-ヺー\s\W]', '', reading)
        if unsupported:
            warnings.append({'text':surface,'start':start,'reason':'辞書で読みを確定できない文字があります。読み指定で補ってください。'})
        units.append({'surface':surface,'reading':reading,'normalized':normalized,'start':start,'end':start+len(surface),'source':source,'reading_uncertain':bool(unsupported)})
    def gap(part, offset):
        for m in tok.tokenize(part, tokenizer.Tokenizer.SplitMode.C):
            reading = m.reading_form()
            if m.part_of_speech()[0] == '助詞' and m.surface() in ('は','へ','を'):
                reading = {'は':'ワ','へ':'エ','を':'オ'}[m.surface()]
            add(m.surface(), reading, offset + m.begin(), 'sudachi')
    cursor=0
    for match in pattern.finditer(text) if pattern else []:
        gap(text[cursor:match.start()], cursor)
        add(match.group(), overrides[match.group()], match.start(), 'user')
        cursor=match.end()
    gap(text[cursor:], cursor)
    expected, mapping = '', []
    for i,u in enumerate(units):
        expected += u['normalized']; mapping.extend([i]*len(u['normalized']))
    expected, _ = normalize(expected)
    return units, expected, mapping, warnings

def align(text, segments, overrides=None):
    units, expected, owners, warnings = expected_readings(text, overrides)
    if not expected: raise ValueError('No usable expected kana; supply Japanese text or --readings')
    actual, positions, raw_text = '', [], ''
    for seg_id, seg in enumerate(segments):
        norm, offsets = normalize(seg['text'])
        base = len(raw_text)
        actual += norm
        positions.extend((seg_id, base + i) for i in offsets)
        raw_text += seg['text']
    actual, _ = normalize(actual)
    matcher=SequenceMatcher(None, expected, actual, autojunk=False)
    opcodes=matcher.get_opcodes()
    groups=[]
    for tag,i1,i2,j1,j2 in opcodes:
        if tag=='equal': continue
        left=owners[min(i1,len(owners)-1)]
        right=owners[i2-1] if i2>i1 else left
        if groups and left <= groups[-1]['right']:
            g=groups[-1];g.update(right=max(g['right'],right),i2=i2,j2=j2)
        else:groups.append(dict(left=left,right=right,i1=i1,i2=i2,j1=j1,j2=j2))
    findings=[]
    boundaries=[]
    for index in range(1,len(segments)):
        offset=next((i for i,p in enumerate(positions) if p[0]==index),len(actual))
        boundaries.append((offset,segments[index]['start_s']))
    for n,g in enumerate(groups,1):
        selected=units[g['left']:g['right']+1]
        # Expand to complete dictionary units, projecting equal spans back to recognition indices.
        a0=owners.index(g['left']);a1=len(owners)-owners[::-1].index(g['right'])
        def project(pos, end=False):
            for tag,i1,i2,j1,j2 in opcodes:
                if i1 <= pos <= i2:
                    if tag=='equal':return j1+pos-i1
                    return j2 if end else j1
            return len(actual)
        b0=min(g['j1'],project(a0));b1=max(g['j2'],project(a1,True))
        b0=max(0,min(b0,len(actual)));b1=max(b0,min(b1,len(actual)))
        near=positions[b0:b1] or positions[max(0,b0-1):max(1,b0)]
        indices=sorted(set(s for s,_ in near))
        if not indices: indices=list(range(len(segments)))
        start=min((segments[i]['start_s'] for i in indices),default=0)
        end=max((segments[i]['end_s'] for i in indices),default=0)
        raw0=positions[b0][1] if b0<len(positions) else len(raw_text)
        raw1=positions[b1-1][1]+1 if b1>b0 else raw0
        nearby=[{'time_s':t,'kana_distance':max(b0-offset,offset-b1,0)} for offset,t in boundaries if max(b0-offset,offset-b1,0)<=6]
        findings.append({'id':f'F{n:03d}','script_start':selected[0]['start'],'script_end':selected[-1]['end'],
            'surface':text[selected[0]['start']:selected[-1]['end']],
            'expected_kana':''.join(u['reading'] for u in selected),
            'observed_kana':raw_text[raw0:raw1], 'expected_normalized':expected[a0:a1],
            'observed_normalized':actual[b0:b1],
            'expected_span':[a0,a1], 'boundary_context':nearby,
            'start_s':round(start,3),'end_s':round(end,3),'time_granularity':'recognition_segment',
            'status':'unreviewed','classification':'読みの差・要聴取',
            'expected_reading_uncertain':any(u['reading_uncertain'] for u in selected),
            'reason':'辞書から得た期待読みとカナASRに差があります。どちらの誤りかは未確定です。'})
    equal=sum(i2-i1 for tag,i1,i2,j1,j2 in opcodes if tag=='equal')
    return {'reading_units':units,'expected_kana':''.join(u['reading'] for u in units),
            'observed_kana':raw_text,'findings':findings,'reading_warnings':warnings,
            'alignment_equal_fraction':equal/max(1,len(expected)),
            'interpretation':'差分は要確認候補です。検出数や一致度は誤読率・音声の正確さを示しません。'}
