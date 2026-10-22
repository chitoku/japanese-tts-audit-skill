"""Project existing alignment findings onto exact original ASR offsets for display only."""
from difflib import SequenceMatcher
import html
from tts_audit.core import normalize

def render_asr(result,visible):
 raw=result['observed_kana'];actual,offsets=normalize(raw)
 expected,owners='',[]
 for i,u in enumerate(result['reading_units']):
  expected+=u['normalized'];owners.extend([i]*len(u['normalized']))
 expected,_=normalize(expected)
 ops=SequenceMatcher(None,expected,actual,autojunk=False).get_opcodes();groups=[]
 for tag,i1,i2,j1,j2 in ops:
  if tag=='equal':continue
  left=owners[min(i1,len(owners)-1)];right=owners[i2-1] if i2>i1 else left
  if groups and left<=groups[-1]['right']:groups[-1].update(right=max(groups[-1]['right'],right),j2=j2)
  else:groups.append(dict(left=left,right=right,j1=j1,j2=j2))
 assert len(groups)==len(result['findings'])
 def project(pos,end=False):
  for tag,i1,i2,j1,j2 in ops:
   if i1<=pos<=i2:return j1+pos-i1 if tag=='equal' else j2 if end else j1
  return len(actual)
 spans=[];valid={f['id'] for f in visible}
 for f,g in zip(result['findings'],groups):
  a0,a1=f['expected_span'];b0=max(0,min(min(g['j1'],project(a0)),len(actual)));b1=max(b0,min(max(g['j2'],project(a1,True)),len(actual)))
  start=offsets[b0] if b0<len(offsets) else len(raw);end=offsets[b1-1]+1 if b1>b0 else start
  assert raw[start:end]==f['observed_kana'],(f['id'],raw[start:end],f['observed_kana'])
  if f['id'] in valid:spans.append((start,end,f['surface']+'：参照 '+f['expected_kana']))
 merged=[]
 for a,b,title in sorted(spans):
  if merged and a<merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]),merged[-1][2]+'／'+title)
  else:merged.append((a,b,title))
 out=[];pos=0
 for a,b,title in merged:
  out.extend([html.escape(raw[pos:a]),'<mark title="'+html.escape(title,quote=True)+'">'+(html.escape(raw[a:b]) if a<b else '［脱落］')+'</mark>']);pos=b
 out.append(html.escape(raw[pos:]));return ''.join(out)
