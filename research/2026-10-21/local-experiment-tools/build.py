from pathlib import Path
import json,hashlib,datetime
from preflight import aliases
ROOT=Path(__file__).resolve().parents[2];W=ROOT/'work/history-200';O=ROOT/'outputs/voicevox-history-200-2026-10-21'
evidence=json.loads((W/'dictionary-evidence.json').read_text());raw=[s.split('\t') for s in (W/'corpus.tsv').read_text().splitlines()]
# Omit ambiguous/context-dependent targets from future candidate sets; never delete evidence or labels.
policy_path=ROOT/'work/reading-review-policy.json';policy=json.loads(policy_path.read_text())
old=ROOT/'outputs/tts-provider-comparison-2026-10-21';notices=json.loads((old/'reading-notices.json').read_text())
# Read exact excluded targets from the already-curated UI, rather than changing user judgments.
import re
page=(old/'index.html').read_text();context=json.loads(re.search(r'const CONTEXT_TERMS=new Set\((\[.*?\])\)',page).group(1))
info=json.loads(re.search(r'const READING_INFO=(.*?);\n',page).group(1));excluded=set(context)|set(policy['explicitly_low_interest_terms'])
for c in json.loads((old/'comparison-index.json').read_text()):
 if any(n['word']==c['target'] for n in info.get(c['id'],{}).get('notices',[])):excluded.add(c['target'])
policy['excluded_targets_for_new_corpora']=sorted(excluded);policy['history_extension']='100 terms / 200 independently authored modern narration sentences; historical context, not authentic Edo quotations; pre-register dictionary alternatives, never score them as abnormal errors.'
policy_path.write_text(json.dumps(policy,ensure_ascii=False,indent=2))
(O/'excluded-targets.json').write_text(json.dumps({'terms':sorted(excluded),'policy':'excluded from new targets; historical samples and human judgments retained'},ensure_ascii=False,indent=2))
extra={'脇本陣':('https://kotobank.jp/word/脇本陣','reference reading; historical inn terminology'), '道中手形':('https://www.mibugishiden.com/word/6-01/','publisher glossary'), '下水路':('JMdict entries 下水 + 路','transparent compound; manually reviewed'), '樽廻船':('https://kotobank.jp/word/樽廻船','reference reading; cargo vessel'), '船箪笥':('https://online.bunka.go.jp/heritages/detail/611158','museum catalogue'), '検地帳':('https://www.city.tateyama.chiba.jp/syougaigaku/page100230.html','municipal museum catalogue'), '千歯扱き':('https://www.city.mihara.hiroshima.jp/soshiki/50/148508.html','municipal museum catalogue')}
categories=['旅と宿場','商家と商い','町割りと建築','職人と道具','町の設備と警備','火消しと暮らし','船と物流','幕府と役人','農業と土地','出版と芸能'];terms=[];sentences=[]
def hira(s):return ''.join(chr(ord(c)-96) if 'ァ'<=c<='ヶ' else c for c in s)
for i,(word,kana,a,b) in enumerate(raw,1):
 assert word not in excluded,word
 entries=evidence.get(word,evidence.get(aliases.get(word,''),[]));accepted=sorted({hira(k) for e in entries for k in e['readings']}|{kana})
 # The alternative dictionary readings are accepted conservatively; no prescriptive-reading test.
 t=dict(id=f'HT{i:03d}',target=word,expected_kana=kana,accepted_readings=accepted,category=categories[(i-1)//10],evidence='observed_video_seed' if word in ['旅籠','呉服屋','金鯱','碁盤割','延床面積'] else 'adjacent_historical_vocabulary_hypothesis',dictionary_entries=entries,reading_source='https://www.edrdg.org/pub/Nihongo/JMdict_e.gz' if entries else extra[word][0],reading_status='JMdict headword/orthographic alias checked' if entries else extra[word][1])
 terms.append(t)
 for j,text in enumerate([a,b],1):
  assert text.count(word)==1,(word,text)
  sentences.append({**{k:v for k,v in t.items() if k!='dictionary_entries'},'term_id':t['id'],'id':f'H{2*i-2+j:04d}','context':j,'text':text,'human_verdict':'unreviewed'})
assert len(terms)==100 and len(sentences)==200 and len({r['text'] for r in sentences})==200
for name,data in [('terms.json',terms),('sentences.json',sentences),('dictionary-evidence.json',evidence)]: (O/name).write_text(json.dumps(data,ensure_ascii=False,indent=2))
(O/'sentences.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in sentences))
manifest=dict(created_at=datetime.datetime.now().astimezone().isoformat(),target_count=100,sentence_count=200,characters=sum(len(r['text']) for r in sentences),source_dictionary='JMdict (EDRDG), downloaded 2026-10-21; supporting museum/publisher references',dictionary_sha256=hashlib.sha256((W/'JMdict_e.gz').read_bytes()).hexdigest(),dictionary_terms=sum(bool(t['dictionary_entries']) for t in terms),accepted_alternatives_not_errors=True,engine='VOICEVOX 0.25.2 青山龍星 ノーマル13',custom_pronunciation=False,corpus_sha256=hashlib.sha256((O/'sentences.json').read_bytes()).hexdigest(),scope='Edo-focused history narration plus relevant building/craft terms; not every word originated in Edo; original authored examples',additional_paid_api_cost_usd=0)
(O/'corpus-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print('READY',len(terms),len(sentences),'excluded',len(excluded),'dictionary',manifest['dictionary_terms'])
