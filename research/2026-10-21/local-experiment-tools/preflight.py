from pathlib import Path
import gzip,xml.etree.ElementTree as ET,json,hashlib,datetime
ROOT=Path(__file__).resolve().parents[2];W=ROOT/'work/history-200';O=ROOT/'outputs/voicevox-history-200-2026-10-21'
rows=[l.split('\t') for l in (W/'corpus.tsv').read_text().splitlines()]
aliases={'碁盤割':'碁盤割り','木挽':'木挽き','町火消':'町火消し','樽廻船':'樽回船','船着場':'船着き場','検地帳':'検地帳','千歯扱き':'千歯扱','船箪笥':'船簞笥'}
terms={r[0] for r in rows}|set(aliases.values());found={}
for event,e in ET.iterparse(gzip.open(W/'JMdict_e.gz'),events=['end']):
 if e.tag!='entry':continue
 keys=[k.text for k in e.findall('k_ele/keb')]
 for k in set(keys)&terms:
  found.setdefault(k,[]).append({'seq':e.findtext('ent_seq'),'spellings':keys,'readings':[x.text for x in e.findall('r_ele/reb')],'glosses':[x.text for x in e.findall('sense/gloss')][:8]})
 e.clear()
(W/'dictionary-evidence.json').write_text(json.dumps(found,ensure_ascii=False,indent=2))
for word,kana,*_ in rows:
 entries=found.get(word,found.get(aliases.get(word,''),[]))
 if not entries:print('NO_ENTRY',word,kana)
 elif kana not in {v for e in entries for v in e['readings']}:print('MISMATCH',word,kana,entries)
