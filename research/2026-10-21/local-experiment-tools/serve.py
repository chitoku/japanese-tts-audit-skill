from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import sys,json,os,re
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[2];O=Path(os.environ.get('TTS_HISTORY_OUT',str(ROOT/'outputs/voicevox-history-200-2026-10-21')))
sys.path.insert(0,str(ROOT/'outputs/release/v0.2.0-beta/japanese-tts-audit-skill/src'))
from tts_audit.server import ReviewStore,Conflict
store=ReviewStore(O)
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def reply(self,code,data=b'',kind='application/json; charset=utf-8',extra=None):
  if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
  self.send_response(code)
  for k,v in {'Content-Type':kind,'Content-Length':str(len(data)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',**(extra or {})}.items():self.send_header(k,v)
  self.end_headers()
  if self.command!='HEAD':self.wfile.write(data)
 def route(self):
  host=f'127.0.0.1:{self.server.server_port}'
  if self.headers.get('Host')!=host or self.headers.get('Origin') not in [None,'http://'+host] or (self.command=='POST' and self.headers.get('Origin')!='http://'+host):self.reply(403,{'error':'origin'});return None
  return urlsplit(self.path).path
 def do_HEAD(self):self.do_GET()
 def do_GET(self):
  p=self.route()
  if p is None:return
  if p=='/api/reviews':return self.reply(200,store.read())
  names={'/':'index.html','/index.html':'index.html','/corpus.html':'corpus.html','/data.json':'review-index.json','/summary.json':'summary.json','/progress.json':'progress.json','/sentences.json':'sentences.json','/excluded-targets.json':'excluded-targets.json'}
  if p in names:
   f=O/names[p]
   if not f.exists():return self.reply(404,{'error':'not ready'})
   return self.reply(200,f.read_bytes(),'text/html; charset=utf-8' if f.suffix=='.html' else 'application/json; charset=utf-8')
  m=re.fullmatch('/samples/(H\\d{4})/audio.wav',p)
  if not m:return self.reply(404)
  f=O/'samples'/m[1]/'audio.wav'
  if not f.is_file() or f.is_symlink():return self.reply(404)
  b=f.read_bytes();h={'Accept-Ranges':'bytes'};rg=self.headers.get('Range')
  if rg:
   r=re.fullmatch(r'bytes=(\d+)-(\d*)',rg)
   if not r:return self.reply(416)
   a=int(r[1]);z=min(int(r[2]),len(b)-1) if r[2] else len(b)-1
   if a>z:return self.reply(416)
   h['Content-Range']=f'bytes {a}-{z}/{len(b)}';return self.reply(206,b[a:z+1],'audio/wav',h)
  self.reply(200,b,'audio/wav',h)
 def do_POST(self):
  p=self.route()
  if p is None:return
  if p!='/api/reviews':return self.reply(404)
  try:
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<1024*1024 or self.headers.get('Content-Type')!='application/json':return self.reply(400)
   self.reply(200,store.update(json.loads(self.rfile.read(size))))
  except Conflict as e:self.reply(409,{'error':str(e)})
  except (ValueError,KeyError):self.reply(400,{'error':'invalid'})
s=ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('TTS_HISTORY_PORT','0'))),H);Path(os.environ.get('TTS_HISTORY_CONFIG',str(ROOT/'work/history-200/server.json'))).write_text(json.dumps({'port':s.server_port,'pid':os.getpid()}));print(f'http://127.0.0.1:{s.server_port}/',flush=True);s.serve_forever()
