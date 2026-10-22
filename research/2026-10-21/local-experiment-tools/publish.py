from pathlib import Path
import json,html,collections,hashlib,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'outputs/release/v0.2.0-beta/japanese-tts-audit-skill/src'))
from tts_audit.core import normalize, align
from highlight import render_asr
ROOT=Path(__file__).resolve().parents[2];O=ROOT/'outputs/voicevox-history-200-2026-10-21'
addenda=json.loads((O/'reading-source-addenda.json').read_text()) if (O/'reading-source-addenda.json').exists() else {};rows=json.loads((O/'sentences.json').read_text());terms=json.loads((O/'terms.json').read_text());items=[];accept_addenda=json.loads((O/'reading-acceptance-addenda.json').read_text()) if (O/'reading-acceptance-addenda.json').exists() else {}
reading_explanations=json.loads((O/'reading-explanations.json').read_text()) if (O/'reading-explanations.json').exists() else {}
context_overrides=json.loads((O/'context-reading-overrides.json').read_text()) if (O/'context-reading-overrides.json').exists() else {}
for row in rows:
 row={**row,'reading_source':addenda.get(row['target'],row['reading_source'])}
 d=O/'samples'/row['id'];p=d/'result.json'
 if not p.exists():continue
 r=json.loads(p.read_text());raw=(d/'audio.wav').read_bytes();assert hashlib.sha256(raw).hexdigest()==r['audio_sha256']
 override=context_overrides.get(row['id'])
 if override:
  row['accepted_readings']=override['accepted_readings'];row['reading_context_note']=override['reason'];row['reading_source']=override['source'] if override['source'].startswith('https://') else row['reading_source']
  # Reclassify stored ASR without new synthesis/ASR or modifying original evidence.
  fresh=align(row['text'],r['segments'],{row['target']:row['expected_kana'],**override.get('readings_override',{})})
  r={**r,**fresh,'comparison_kana':row['expected_kana'],'accepted_reading_matched':[k for k in row['accepted_readings'] if normalize(k)[0] in normalize(r['observed_kana'])[0]],'engine_target_reading_present':any(normalize(k)[0] in normalize(r['engine_planned_kana'])[0] for k in row['accepted_readings'])}
  a=row['text'].index(row['target']);b=a+len(row['target']);r['target_findings']=[f for f in r['findings'] if f['script_start']<b and f['script_end']>a]
  directory=O/'reclassified-results';directory.mkdir(exist_ok=True);(directory/(row['id']+'.json')).write_text(json.dumps({'basis':override,'result':r},ensure_ascii=False,indent=2))
 accepted=list(dict.fromkeys(row['accepted_readings']+accept_addenda.get(row['target'],{}).get('accepted_readings',[])));row['accepted_readings']=accepted
 suppressed=[f for f in r['target_findings'] if normalize(f['observed_kana'])[0] in {normalize(k)[0] for k in accepted}]
 fs=[f for f in r['target_findings'] if f not in suppressed];others=[f for f in r['findings'] if f not in fs and f not in suppressed]
 # Accepted dictionary alternatives are already used as the reference by run.py.
 target_diff=bool(fs) and not r['accepted_reading_matched']
 engine_diff=not r['engine_target_reading_present']
 rank=100 if target_diff and engine_diff else 70 if target_diff else 40 if others else 0
 reason='対象語でASR差分があり、エンジンの予定読みも参照読みと不一致' if rank==100 else '対象語のASRに差。予定読みは参照内なので、音の弱さ・ASR誤認も疑う' if rank==70 else '対象語以外の機械差分。読み分けやASR誤認を含む' if rank==40 else '対象語・文中とも機械差分なしの対照'
 matched=list(dict.fromkeys(r['accepted_reading_matched']+[k for k in accepted for f in suppressed if normalize(k)[0]==normalize(f['observed_kana'])[0]]))
 alternatives=[k for k in matched if normalize(k)[0]!=normalize(row['expected_kana'])[0]]
 explanation=None
 if alternatives and not target_diff:
  detail=reading_explanations.get(row['target'],{})
  explanation={'initial_reference':row['expected_kana'],'matched_accepted_readings':alternatives,'comparison_kana':r['comparison_kana'],'handling':'difference_suppressed' if suppressed else 'comparison_reference_switched','reason':detail.get('reason','辞書・補足資料に掲載された別読みとして、現在の照合設定で許容しています。'),'source':detail.get('source',accept_addenda.get(row['target'],{}).get('source',row['reading_source']))}
 items.append({**row,'comparison_kana':r['comparison_kana'],'reading_explanation':explanation,'asr':r['segments'][0]['text'],'asr_html':render_asr(r,[f for f in r['findings'] if f not in suppressed]),'planned':r['engine_planned_kana'],'target_difference':target_diff,'other_findings':others,'target_findings':fs,'findings':[f for f in r['findings'] if f not in suppressed],'accepted_alternative_findings_suppressed':suppressed,'engine_difference':engine_diff,'score':rank,'reason':reason,'duration_s':r['duration_s'],'accepted_reading_matched':r['accepted_reading_matched']})
items.sort(key=lambda r:(-r['score'],r['term_id'],r['context']));(O/'review-index.json').write_text(json.dumps(items,ensure_ascii=False,indent=2))
# Immutable set of valid sentence IDs for atomic ReviewStore; published results may grow, IDs do not change.
manifest={'schema_version':1,'run_id':'voicevox-history-200-v1','findings':[{'id':r['id'],'surface':r['target']} for r in rows]}
p=O/'report.json'
if p.exists():assert json.loads(p.read_text())==manifest
else:p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
seen=set();priority=[]
for row in items:
 if row['term_id'] in seen or not row['target_difference']:continue
 seen.add(row['term_id']);priority.append(row['id'])
summary={'total':200,'processed':len(items),'target_difference_sentences':sum(r['target_difference'] for r in items),'target_difference_terms':len(priority),'other_only_sentences':sum(r['score']==40 for r in items),'no_difference_sentences':sum(r['score']==0 for r in items),'high_priority_ids':priority[:20],'priority_sentence_ids':priority,'audio_duration_s':sum(r['duration_s'] for r in items),'first_pass_duration_s':sum(r['duration_s'] for r in items if r['id'] in priority),'first_pass_planned_difference_terms':sum(r['engine_difference'] for r in items if r['id'] in priority),'first_pass_phonetic_or_asr_terms':sum(not r['engine_difference'] for r in items if r['id'] in priority),'human_listening_status':'not counted here; read review-state.json','status':'complete' if len(items)==200 else 'processing','paid_api_cost_usd':0,'warning':'Machine candidates only, not confirmed pronunciation errors; alternatives accepted before scoring.'}
(O/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
e=html.escape
parts=['<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>歴史語彙100語・200文</title><style>body{font:17px/1.8 system-ui;max-width:950px;margin:auto;padding:20px}article{border-bottom:1px solid #ccc;padding:12px}small{color:#556}a{color:#175e46}</style><h1>歴史語彙100語・200文</h1><p>江戸時代を中心とする歴史解説用の新作文です。実際に報告された誤読を起点に関連語を展開しました。全100語が観測済み誤読という意味ではありません。延床面積など、歴史建築の解説に使う現代語も含みます。</p><p>JMdictの掲載読みを照合し、表記違いも確認。辞書の別読みは許容し、違いとして聴取を求めません。追加資料は各語のリンク参照。人による音声確認は未実施です。</p><p><a href="./">聴取リストへ</a> ／ <a href="sentences.json">JSON</a></p>']
for t in terms:
 t={**t,'reading_source':addenda.get(t['target'],t['reading_source']),'accepted_readings':list(dict.fromkeys(t['accepted_readings']+accept_addenda.get(t['target'],{}).get('accepted_readings',[])))}
 rs=[r for r in rows if r['term_id']==t['id']];parts.append(f'<article><h2>{e(t["id"])} {e(t["target"])}：{e(t["expected_kana"])}</h2><small>{e(t["category"])} ／ 許容読み：{e("、".join(t["accepted_readings"]))} ／ <a href="{e(t["reading_source"])}">読みの根拠</a></small>'+''.join(f'<p>{e(r["id"])} {e(r["text"])}</p>' for r in rs)+'</article>')
parts.append('<p>辞書参照：JMdict / Electronic Dictionary Research and Development Group。辞書データ © James William BREEN / EDRDG。<a href="https://www.edrdg.org/edrdg/licence.html">CC BY-SA 4.0・利用条件</a>。例文は本調査で新規作成。音声：VOICEVOX 青山龍星。</p>');(O/'corpus.html').write_text(''.join(parts))
print(json.dumps(summary,ensure_ascii=False))
