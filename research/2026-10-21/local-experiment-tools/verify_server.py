from pathlib import Path
import json,subprocess,os,time,urllib.request,urllib.error,shutil,datetime
R=Path(__file__).resolve().parents[2];W=R/'work/history-200';qa=W/'qa';qa.mkdir(exist_ok=True);source=R/'outputs/voicevox-history-200-2026-10-21'
for name in ['index.html','report.json','summary.json','review-index.json']:shutil.copyfile(source/name,qa/name)
d=qa/'samples/H0001';d.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/'samples/H0001/audio.wav',d/'audio.wav')
config=W/'qa-server.json';config.unlink(missing_ok=True)
env={**os.environ,'TTS_HISTORY_OUT':str(qa),'TTS_HISTORY_CONFIG':str(config),'PYTHONPATH':str(R/'work/corpus-1000/mlx-runtime')}
p=subprocess.Popen([str(R/'work/release-prep/clean-venv/bin/python'),str(W/'serve.py')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
try:
 for _ in range(100):
  if config.exists():break
  time.sleep(.05)
 port=json.loads(config.read_text())['port'];base=f'http://127.0.0.1:{port}'
 def req(path,body=None,headers=None):
  if body is not None:body=json.dumps(body).encode()
  h=headers or {}
  if body is not None:h={**h,'Origin':base,'Content-Type':'application/json'}
  try:
   with urllib.request.urlopen(urllib.request.Request(base+path,data=body,headers=h)) as r:return r.status,r.read(),dict(r.headers)
  except urllib.error.HTTPError as e:return e.code,e.read(),dict(e.headers)
 assert req('/')[0]==200
 status,a,h=req('/samples/H0001/audio.wav',headers={'Range':'bytes=0-99'});assert status==206 and len(a)==100
 state=json.loads(req('/api/reviews')[1]);body={'schema_version':1,'run_id':state['run_id'],'revision':state['revision'],'notes':{'H0001':{'verdict':'uncertain','heard':'QA','note':'temporary isolated fixture','updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}}}
 assert req('/api/reviews',body)[0]==200
 assert req('/api/reviews',body)[0]==409
 assert json.loads(req('/api/reviews')[1])['notes']['H0001']['heard']=='QA'
 assert req('/../work/youtube-api-key.txt')[0]==404
 assert req('/api/reviews',headers={'Origin':'https://unrelated.example'})[0]==403
 result={'passed':True,'checks':['HTML and JSON serving','audio range 206','atomic saved judgment reads back','stale revision 409 preserves notes','path allowlist','foreign origin rejected'],'production_judgments_written':False};(W/'server-verification.json').write_text(json.dumps(result,indent=2));print(result)
finally:p.terminate();p.wait(timeout=10)
