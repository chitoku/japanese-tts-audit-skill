"""Checkpointed local-only 200-sentence history pilot, no input text supplied to ASR."""
from pathlib import Path
import sys,os,json,time,hashlib,urllib.request,urllib.parse,traceback,threading
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/voicevox-history-200-2026-10-21'
sys.path.insert(0,str(ROOT/'outputs/release/v0.2.0-beta/japanese-tts-audit-skill/src'))
from tts_audit.core import align,normalize
from tts_audit.cli import load_audio
rows=json.loads((OUT/'sentences.json').read_text());start=time.time();stats={'generated':0,'recognized':0,'failed':[]};lock=threading.Lock()
def write(p,obj):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(obj,ensure_ascii=False,indent=2));t.replace(p)
def sha(b):return hashlib.sha256(b).hexdigest()
def progress(phase):
 with lock:write(OUT/'progress.json',{'phase':phase,**stats,'total':len(rows),'elapsed_s':round(time.time()-start,1),'updated_at':time.time(),'paid_api_cost_usd':0})
def api(endpoint,params,body=None):
 req=urllib.request.Request('http://127.0.0.1:50021'+endpoint+'?'+urllib.parse.urlencode(params),data=json.dumps(body).encode() if body else b'',headers={'Content-Type':'application/json'})
 return urllib.request.urlopen(req,timeout=180).read()
version=json.load(urllib.request.urlopen('http://127.0.0.1:50021/version'));assert version=='0.25.2'
def synth(row):
 d=OUT/'samples'/row['id'];d.mkdir(parents=True,exist_ok=True);script=d/'script.txt'
 if script.exists():assert script.read_text()==row['text']
 else:script.write_text(row['text'])
 if not (d/'audio.wav').exists():
  q=json.loads(api('/audio_query',{'text':row['text'],'speaker':13}));write(d/'query.json',q);raw=api('/synthesis',{'speaker':13},q)
  t=d/'audio.wav.tmp';t.write_bytes(raw);t.replace(d/'audio.wav');write(d/'generation.json',dict(engine_version=version,voice='青山龍星',style_id=13,custom_readings=False,script_sha256=sha(row['text'].encode()),audio_sha256=sha(raw),paid_api_cost_usd=0))
 with lock:stats['generated']+=1
 progress('generating_and_recognizing');return row
producer_errors=[]
def produce():
 try:
  with ThreadPoolExecutor(max_workers=1) as pool:
   for i,_ in enumerate(pool.map(synth,rows),1):
    if i%25==0:print('Generated',i,'/200',flush=True)
 except Exception as e:producer_errors.append(repr(e));traceback.print_exc()
thread=threading.Thread(target=produce);thread.start()
import mlx_whisper,mlx.core as mx,numpy as np
from mlx_whisper.transcribe import ModelHolder
model=ROOT/'work/corpus-1000/kana-whisper-mlx-fp32';proof=json.loads((ROOT/'work/corpus-1000/mlx-weight-verification.json').read_text());assert proof['all_converted_parameter_tensors_exactly_equal']
m=ModelHolder.get_model(str(model),mx.float32);m.encoder._positional_embedding=mx.array(np.load(model/'encoder-position-source.npy'));mx.eval(m.encoder._positional_embedding)
write(OUT/'execution.json',dict(engine_version=version,style_id=13,voice='青山龍星',asr=proof,backend='mlx-whisper float32',model='sbintuitions/kana-whisper',script_supplied_to_asr=False,external_audio_upload=False,paid_api_cost_usd=0,independent_per_sentence=True,corpus_sha256=sha((OUT/'sentences.json').read_bytes()),runner_sha256=sha(Path(__file__).read_bytes())))
for row in rows:
 d=OUT/'samples'/row['id']
 try:
  while not (d/'audio.wav').exists():
   if producer_errors:raise RuntimeError(producer_errors)
   time.sleep(.25)
  raw=(d/'audio.wav').read_bytes();ah=sha(raw)
  if (d/'result.json').exists():
   assert json.loads((d/'result.json').read_text())['audio_sha256']==ah
   stats['recognized']+=1;continue
  if (d/'transcript.json').exists():tr=json.loads((d/'transcript.json').read_text());assert tr['audio_sha256']==ah
  else:
   a=load_audio(d/'audio.wav');t=time.time();asr=mlx_whisper.transcribe(a,path_or_hf_repo=str(model),language='ja',task='transcribe',fp16=False,temperature=0,condition_on_previous_text=False,verbose=None,word_timestamps=False)
   assert normalize(asr['text'])[0]
   tr={'audio_sha256':ah,'segments':[{'text':asr['text'],'start_s':0,'end_s':len(a)/16000}],'elapsed_s':time.time()-t};write(d/'transcript.json',tr)
  obs=normalize(tr['segments'][0]['text'])[0]
  canonical=normalize(row['expected_kana'])[0]
  matched=[k for k in row['accepted_readings'] if normalize(k)[0] in obs]
  selected=row['expected_kana'] if canonical in obs or not matched else max(matched,key=len)
  result=align(row['text'],tr['segments'],{row['target']:selected})
  q=json.loads((d/'query.json').read_text());planned=''.join(m['text'] for p in q['accent_phrases'] for m in p['moras']);pn=normalize(planned)[0]
  target_findings=[f for f in result['findings'] if f['surface']==row['target'] or (f.get('script_start',-1)<row['text'].index(row['target'])+len(row['target']) and f.get('script_end',-1)>row['text'].index(row['target']))]
  result.update(script=row['text'],sentence_id=row['id'],target=row['target'],reference_kana=row['expected_kana'],comparison_kana=selected,accepted_readings=row['accepted_readings'],accepted_reading_matched=matched,engine_planned_kana=planned,engine_target_reading_present=any(normalize(k)[0] in pn for k in row['accepted_readings']),audio_sha256=ah,segments=tr['segments'],duration_s=tr['segments'][0]['end_s'],target_findings=target_findings,script_supplied_to_asr=False)
  write(d/'result.json',result);stats['recognized']+=1;progress('generating_and_recognizing')
  if stats['recognized']%20==0:print('Recognized',stats['recognized'],'/200',round(time.time()-start,1),'s',flush=True)
 except Exception as e:stats['failed'].append({'id':row['id'],'error':repr(e)});traceback.print_exc();progress('continuing_after_failure')
thread.join();progress('failed' if stats['failed'] or producer_errors else 'complete');print('COMPLETE',stats,flush=True)
