"""Versioned sentence audio: provider-neutral import, local audit, explicit adoption."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from html import escape as H
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from types import SimpleNamespace
import uuid

RATE = .0003  # Conservative reserve, not an invoice or a current price quote.


def now(): return datetime.now(timezone.utc).isoformat()
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def text_digest(text): return hashlib.sha256(text.encode('utf-8')).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    temp = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def split_sentences(text):
    # Fullwidth Japanese sentence endings; manual segmentation can override this.
    pieces = [m.group().strip() for m in re.finditer(r'.+?(?:[。！？!?]+[」』”’）)]*|$)', text, re.S)]
    pieces = [p for p in pieces if p]
    if not pieces: raise ValueError('Script is empty')
    if ''.join(''.join(pieces).split()) != ''.join(text.split()): raise ValueError('Sentence split lost text')
    return pieces


@contextmanager
def locked(root):
    root = Path(root).resolve()
    lock = root / '.mutation-lock'
    try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError: raise ValueError('Project is in use or has an interrupted mutation; inspect .mutation-lock before continuing')
    try:
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        yield root
    finally: lock.unlink(missing_ok=True)


def local(root, path):
    result = (root / path).resolve()
    if not result.is_relative_to(root.resolve()): raise ValueError('Project path escapes its directory')
    return result


def version(sentence, ident=None):
    ident = ident or sentence['selected_version']
    if ident == 'latest':
        if not sentence['versions']: raise ValueError('No generated audio')
        return sentence['versions'][-1]
    return next((v for v in sentence['versions'] if v['id'] == ident), None)


def load(root):
    d = read(root / 'project.json')
    if d.get('schema_version') != 1: raise ValueError('Unsupported project schema')
    if digest(root / 'canonical-script.txt') != d['script_sha256']: raise ValueError('Canonical script changed; initialize a new project')
    if d.get('readings_sha256') and digest(root/'readings.json')!=d['readings_sha256']:raise ValueError('Expected readings changed; initialize a new project')
    for s in d['sentences']:
        if text_digest(s['canonical_text']) != s['canonical_sha256']: raise ValueError('Canonical sentence changed')
        if local(root, s['script_file']).read_text(encoding='utf-8') != s['canonical_text']: raise ValueError('Sentence script changed')
        for v in s['versions']:
            if digest(local(root,v['audio'])) != v['audio_sha256']: raise ValueError('Sentence audio changed: ' + s['id'] + '/' + v['id'])
            if v.get('provider_audio') and digest(local(root,v['provider_audio'])) != v['provider_audio_sha256']: raise ValueError('Original provider audio changed')
            if text_digest(v['generation_text']) != v['generation_text_sha256']: raise ValueError('Generation text changed')
            if digest(local(root,v['audio']).parent/'generation.txt') != v['generation_text_sha256']: raise ValueError('Saved generation text changed')
            if v.get('audit'):
                audit = read(local(root, v['audit']))
                if audit['audio_sha256'] != v['audio_sha256'] or audit['script_sha256'] != s['canonical_sha256']: raise ValueError('Audit does not match audio or script')
            if v.get('review') and v['review']['audio_sha256'] != v['audio_sha256']: raise ValueError('Review does not match audio')
    return d


def budget(d):
    if d.get('provider','elevenlabs') != 'elevenlabs':
        return {'tracking':'external_untracked','note':'Generation and spending are managed by the existing service/agent, not this CLI.'}
    reserved = sum(x['reserved_usd'] for x in d['requests'])
    b = d['budget']
    return {'new_reserved_usd': round(reserved,7), 'combined_reserved_usd': round(b['baseline_usd']+reserved,7),
            'limit_usd': b['limit_usd'], 'remaining_usd': round(b['limit_usd']-b['baseline_usd']-reserved,7)}


def find_sentence(d, ident):
    s = next((s for s in d['sentences'] if s['id'] == ident), None)
    if s is None: raise ValueError('Unknown sentence ID: ' + ident)
    return s


def chosen(d, ids):
    if ids and len(set(ids))!=len(ids):raise ValueError('Duplicate sentence IDs')
    return [find_sentence(d, i) for i in ids] if ids else d['sentences']


def save(root, d):
    d['tool_version']=__import__('tts_audit').__version__
    d['updated_at'] = now(); write(root/'project.json', d)
    render_project(root, d)


def render_project(root, d):
    rows=[]
    for s in d['sentences']:
        active=version(s)
        history=[]
        for v in s['versions']:
            label='採用中' if v['id']==s['selected_version'] else '旧版・候補'
            verdict=v.get('review',{}).get('verdict','unreviewed')
            basis=v.get('review',{}).get('basis','—')
            input_label='生成用入力（元台本と同じと仮定）' if v.get('provenance',{}).get('generation_text_basis')=='canonical_assumed' else '生成用入力'
            audit=f'<a href="{H(v["audit"].replace("report.json","report.html"))}">文の点検レポート</a>' if v.get('audit') else '未点検'
            history.append(f'<div class="version"><b>{H(v["id"])}・{label}／{H(verdict)}（{H(basis)}）</b><p>{input_label}：{H(v["generation_text"])}</p><audio controls preload="none" src="{H(v["audio"])}"></audio><p>{audit}</p><small>SHA-256 {v["audio_sha256"]}</small></div>')
        rows.append(f'<section><h2>{s["id"]}</h2><p>{H(s["canonical_text"])}</p>'+''.join(history or ['<p>音声未生成</p>'])+'</section>')
    b=budget(d)
    budget_html=(f"予算計上：累計 ${b['combined_reserved_usd']:.4f} / ${b['limit_usd']:.2f}。今回の予算計上 ${b['new_reserved_usd']:.4f}。料金の請求額ではありません。"
                 if b.get('tracking')!='external_untracked' else '生成・再生成と費用の確認は、エージェントが既存の制作サービスで行います。このCLIは外部サービスの費用を集計しません。')
    html=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>文単位の制作・点検</title><style>body{{font-family:-apple-system,sans-serif;background:#eff4ef;color:#254133;line-height:1.8}}main{{max-width:1000px;margin:auto;padding:24px}}section,.version{{background:white;border:1px solid #ccddcc;border-radius:10px;padding:18px;margin:18px 0}}.version{{background:#f8fbf8}}audio{{width:100%}}small{{overflow-wrap:anywhere}}a{{color:#176647}}</style><main><h1>文単位の制作・点検</h1><p>{len(d['sentences'])}文。生成と採用は別操作です。新しい版を生成しても、確認済みの採用版を自動で変更しません。</p><p>{budget_html}</p><p>approvedは記録された根拠（human / asr / agent）と一緒に確認してください。ASR根拠の採用を人の聴取済みとは扱いません。文の採用判定はCLIで記録します。個別レポートの聴取メモは、確認サーバー利用時は自動保存、ファイルで開く場合はJSONで書き出します。</p>{''.join(rows)}</main><script>{player_js()}</script></html>'''
    (root/'index.html').write_text(html,encoding='utf-8')


def player_js():
    return "const aa=[...document.querySelectorAll('audio')];let current=aa[0];aa.forEach(a=>{a.onplay=()=>{current=a;aa.forEach(b=>{if(a!==b)b.pause()})};a.onpointerdown=()=>current=a});document.addEventListener('keydown',e=>{if(e.code!=='Space'||e.repeat||e.ctrlKey||e.metaKey||e.altKey||e.target.closest('input,textarea,select,[contenteditable=true]'))return;e.preventDefault();if(current){if(current.paused)current.play().catch(()=>{});else current.pause()}});"


def source_metadata(path):
    if path is None:return None
    data=read(path)
    allowed={'provider','model','voice','settings','project_reference'}
    if not isinstance(data,dict) or not data or set(data)-allowed:
        raise ValueError('Source JSON must contain provider/model/voice/settings/project_reference metadata only; never credentials')
    for key in allowed-{'settings'}:
        if key in data and (not isinstance(data[key],str) or not data[key].strip()):
            raise ValueError('Source '+key+' must be a nonempty string')
    if 'settings' in data and not isinstance(data['settings'],dict):raise ValueError('Source settings must be an object')
    return data


def init(args):
    root=args.out.resolve()
    if root.exists(): raise ValueError('Project output exists; use a new directory')
    # Preserve old explicit ElevenLabs invocation while making the default neutral.
    mode=getattr(args,'provider',None) or ('elevenlabs' if args.voice_id else 'external')
    source=source_metadata(getattr(args,'source_json',None))
    model=voice=None;limits=None
    if mode=='elevenlabs':
        if args.budget_usd is None or args.max_new_usd is None:raise ValueError('ElevenLabs generation requires --budget-usd and --max-new-usd')
        if not all(math.isfinite(x) for x in [args.budget_usd,args.baseline_usd,args.max_new_usd]): raise ValueError('Budget must be finite')
        if not 0<=args.baseline_usd<args.budget_usd or args.max_new_usd<=0: raise ValueError('Invalid budget')
        if not args.voice_id or not re.fullmatch(r'[A-Za-z0-9_-]+',args.voice_id):raise ValueError('Invalid voice ID')
        model=args.model or 'eleven_v3';voice=args.voice_id
        if model not in {'eleven_v3','eleven_multilingual_v2'}:raise ValueError('Unsupported built-in ElevenLabs model')
        if source is not None:raise ValueError('--source-json belongs to external projects; built-in ElevenLabs settings use --model/--voice-id')
        source={'provider':'ElevenLabs','model':model,'voice':voice}
        limits={'limit_usd':args.budget_usd,'baseline_usd':args.baseline_usd,'max_new_usd':args.max_new_usd,'reserve_per_character_usd':RATE}
    elif mode=='external':
        if args.model or args.voice_id or args.budget_usd is not None or args.max_new_usd is not None or args.baseline_usd:
            raise ValueError('External projects use --source-json; spending is managed outside this CLI')
        source=source or {'provider':'external'}
    else:raise ValueError('Unsupported project provider mode')
    text=args.script.read_text(encoding='utf-8-sig')
    pieces=read(args.sentences_json) if args.sentences_json else split_sentences(text)
    if not isinstance(pieces,list) or not pieces or any(not isinstance(p,str) or not p.strip() for p in pieces): raise ValueError('Sentences JSON must contain nonempty strings')
    if ''.join(''.join(pieces).split())!=''.join(text.split()): raise ValueError('Manual sentences must preserve the canonical script')
    root.parent.mkdir(parents=True,exist_ok=True)
    tmp=Path(tempfile.mkdtemp(prefix='.sentence-project-',dir=root.parent))
    try:
        (tmp/'canonical-script.txt').write_text(text,encoding='utf-8')
        readings=read(args.readings) if args.readings else {}
        from .core import expected_readings
        expected_readings(text,readings)  # Validate before creating a project or spending anything.
        write(tmp/'readings.json',readings)
        d={'schema_version':1,'tool_version':__import__('tts_audit').__version__,'project_id':str(uuid.uuid4()),'created_at':now(),
           'script_sha256':digest(tmp/'canonical-script.txt'),'readings_sha256':digest(tmp/'readings.json'),
           'provider':mode,'source':source,'model':model,'voice_id':voice,'budget':limits,
           'requests':[],'sentences':[],'events':[]}
        for i,text in enumerate(pieces,1):
            ident=f'S{i:03d}';folder=tmp/'sentences'/ident;folder.mkdir(parents=True)
            (folder/'canonical.txt').write_text(text,encoding='utf-8')
            d['sentences'].append({'id':ident,'canonical_text':text,'canonical_sha256':text_digest(text),
                                  'script_file':f'sentences/{ident}/canonical.txt','selected_version':None,'versions':[]})
        save(tmp,d);tmp.rename(root)
    except Exception: shutil.rmtree(tmp);raise
    return {'project':str(root),'sentences':len(pieces),'budget':budget(d)}


def elevenlabs(text, d, key_file):
    import requests
    key=Path(key_file).read_text(encoding='utf-8').strip()
    if not key: raise ValueError('Empty key file')
    try:
        sub=requests.get('https://api.elevenlabs.io/v1/user/subscription',headers={'xi-api-key':key},timeout=30)
        if not sub.ok: raise RuntimeError('Subscription HTTP '+str(sub.status_code))
        usage=sub.json()
        if usage['character_limit']-usage['character_count']<(len(text)+1)*2: raise ValueError('Insufficient included credits; no generation requested')
        response=requests.post('https://api.elevenlabs.io/v1/text-to-speech/'+d['voice_id'],
            params={'output_format':'mp3_44100_128'},headers={'xi-api-key':key,'Content-Type':'application/json'},
            json={'text':text,'model_id':d['model']},timeout=(30,150))
        if not response.ok: raise RuntimeError('Generation HTTP '+str(response.status_code))
        if not response.headers.get('Content-Type','').startswith('audio/'): raise RuntimeError('Provider did not return audio')
        return response.content,{'character_cost':response.headers.get('character-cost'), 'request_id':response.headers.get('request-id')}
    except requests.RequestException: raise RuntimeError('Network outcome uncertain; reservation retained; no automatic retry') from None


def store_version(root,d,s,text,raw,provenance):
    from .cli import load_audio
    import soundfile as sf
    ident=f'v{len(s["versions"])+1:03d}'
    folder=root/'sentences'/s['id']/ident
    if folder.exists(): raise ValueError('Version directory exists; inspect interrupted generation')
    folder.mkdir()
    try:
        source=folder/('provider.wav' if raw.startswith(b'RIFF') else 'provider.mp3')
        source.write_bytes(raw)
        decoded=load_audio(source)
        sf.write(folder/'audio.wav',decoded,16000,subtype='PCM_16')
        (folder/'generation.txt').write_text(text,encoding='utf-8')
        v={'id':ident,'created_at':now(),'generation_text':text,'generation_text_sha256':text_digest(text),
           'audio':str((folder/'audio.wav').relative_to(root)),'audio_sha256':digest(folder/'audio.wav'),
           'provider_audio':str(source.relative_to(root)),'provider_audio_sha256':digest(source),
           'duration_s':len(decoded)/16000,'provenance':provenance}
        s['versions'].append(v)
        if s['selected_version'] is None:s['selected_version']=ident
        return v
    except Exception:
        shutil.rmtree(folder);raise


def generate(args,provider=None):
    provider=provider or elevenlabs
    with locked(args.project) as root:
        d=load(root)
        if d.get('provider','elevenlabs')!='elevenlabs':
            raise ValueError('External project: regenerate with the existing service/agent, then use import-audio; no built-in provider request sent')
        if any(r['outcome'] in {'reserved','uncertain'} for r in d['requests']): raise ValueError('Unresolved generation request; reconcile provider outcome before any paid retry')
        selected=chosen(d,args.sentence)
        if args.regenerate:
            if len(selected)!=1 or not args.text_file: raise ValueError('Regeneration needs one --sentence and --text-file')
            active=version(selected[0])
            if not active or active.get('review',{}).get('verdict')!='needs_revision': raise ValueError('Only a sentence marked needs_revision may be regenerated; approved audio is retained')
            todo=[(selected[0],args.text_file.read_text(encoding='utf-8-sig').strip())]
        else:
            if args.text_file: raise ValueError('--text-file requires --regenerate')
            todo=[(s,s['canonical_text']) for s in selected if not s['versions']]
        if len(todo)>args.max_requests: raise ValueError('Request limit too small; no request sent')
        if any(not text for _,text in todo):raise ValueError('Generation text is empty')
        projected=sum((len(text)+1)*RATE for _,text in todo)
        b=budget(d)
        if b['new_reserved_usd']+projected>d['budget']['max_new_usd']+1e-9 or projected>b['remaining_usd']+1e-9: raise ValueError('Budget guard: no request sent')
        if not args.key_file:raise ValueError('--key-file is required for paid generation')
        completed=[]
        for s,text in todo:
            request={'id':str(uuid.uuid4()),'sentence_id':s['id'],'utc':now(),'reserved_usd':round((len(text)+1)*RATE,7),'outcome':'reserved','generation_text_sha256':text_digest(text)}
            d['requests'].append(request);save(root,d) # Persist reservation before any external request.
            try:
                raw,meta=provider(text,d,args.key_file)
                request.update(provider=meta)
                if meta.get('character_cost') is not None:
                    credits=float(meta['character_cost'])
                    if not math.isfinite(credits) or credits<0: raise ValueError('Invalid provider credit cost')
                    request['reserved_usd']=max(request['reserved_usd'],round(credits*RATE,7))
                v=store_version(root,d,s,text,raw,{'kind':'generated','model':d['model'],'voice_id':d['voice_id'],'request_id':request['id'],'provider':meta})
                request.update(outcome='completed',version_id=v['id']);completed.append(s['id']+'/'+v['id'])
                save(root,d)
                if budget(d)['new_reserved_usd']>d['budget']['max_new_usd'] or budget(d)['remaining_usd']<0:raise ValueError('Provider usage exceeded reservation; stopped before any further request')
            except Exception:
                if request['outcome']!='completed':request['outcome']='uncertain'
                save(root,d);raise
        return {'generated':completed,'budget':budget(d)}


def attach(args):
    if not args.note.strip():raise ValueError('Provide import provenance in --note')
    source=source_metadata(getattr(args,'source_json',None))
    with locked(args.project) as root:
        d=load(root);s=find_sentence(d,args.sentence)
        text_file=getattr(args,'text_file',None)
        text=text_file.read_text(encoding='utf-8-sig').strip() if text_file else s['canonical_text']
        if not text:raise ValueError('Generation text is empty')
        v=store_version(root,d,s,text,args.audio.read_bytes(),{'kind':'imported','source_audio_sha256':digest(args.audio),
            'source':source if source is not None else d.get('source'),
            'generation_text_basis':'provided' if text_file else 'canonical_assumed','note':args.note})
        save(root,d);return {'imported':s['id']+'/'+v['id'],'selected_version':s['selected_version']}


def audit(args):
    from .cli import Recognizer,check
    with locked(args.project) as root:
        d=load(root);recognizer=None;done=[]
        for s in chosen(d,args.sentence):
            v=version(s,args.version)
            if not v:raise ValueError('No audio for '+s['id'])
            if v.get('audit'):continue
            recognizer=recognizer or Recognizer(args)
            out=local(root,v['audio']).parent/'audit'
            options=SimpleNamespace(audio=local(root,v['audio']),script=local(root,s['script_file']),out=out,readings=root/'readings.json',
                transcript_json=None,cache_dir=args.cache_dir,offline=args.offline,device=args.device,chunk_seconds=18,boundary_recheck=True)
            check(options,recognizer)
            result=read(out/'report.json')
            v.update(audit=str((out/'report.json').relative_to(root)),audit_run_id=result['run_id'])
            done.append(s['id']+'/'+v['id']);save(root,d)
        return {'checked':done}


def review(args):
    if not args.note.strip():raise ValueError('Provide a review note and its basis')
    with locked(args.project) as root:
        d=load(root);s=find_sentence(d,args.sentence);v=version(s,args.version)
        if not v or not v.get('audit'):raise ValueError('Check this version before recording an adoption review')
        v['review']={'verdict':args.verdict,'basis':args.basis,'note':args.note,'audio_sha256':v['audio_sha256'],'audit_run_id':v['audit_run_id'],'updated_at':now()}
        d['events'].append({'kind':'review','sentence':s['id'],'version':v['id'],**v['review']})
        save(root,d);return {'sentence':s['id'],'version':v['id'],'review':v['review']}


def select(args):
    with locked(args.project) as root:
        d=load(root);s=find_sentence(d,args.sentence);v=version(s,args.version)
        if not v or v.get('review',{}).get('verdict')!='approved':raise ValueError('Candidate version must be checked and approved before adoption')
        old=s['selected_version'];s['selected_version']=v['id']
        d['events'].append({'kind':'select','sentence':s['id'],'from':old,'to':v['id'],'utc':now()})
        save(root,d);return {'sentence':s['id'],'previous':old,'selected':v['id']}


def assemble(args):
    import numpy as np
    import soundfile as sf
    with locked(args.project) as root:
        d=load(root);out=args.out.resolve()
        if out.exists():raise ValueError('Assembly output exists; choose a new directory')
        if not math.isfinite(args.gap_ms) or not 0<=args.gap_ms<=3000:raise ValueError('gap-ms must be 0..3000')
        chunks=[];timeline=[];cursor=0;gap=np.zeros(round(args.gap_ms*16),dtype=np.int16)
        for i,s in enumerate(d['sentences']):
            v=version(s)
            if not v or (v.get('review',{}).get('verdict')!='approved' and not args.preview):raise ValueError('Every selected sentence must be approved before assembly; --preview allows a clearly labeled listening draft')
            a,sr=sf.read(local(root,v['audio']),dtype='int16')
            if sr!=16000 or a.ndim!=1:raise ValueError('Project audio must be mono PCM at 16 kHz')
            if i:chunks.append(gap);cursor+=len(gap)
            timeline.append({'sentence_id':s['id'],'version_id':v['id'],'source_audio_sha256':v['audio_sha256'],
                'review_basis':v.get('review',{}).get('basis'),'review_verdict':v.get('review',{}).get('verdict','unreviewed'),'start_sample':cursor,'end_sample':cursor+len(a),'canonical_text':s['canonical_text']})
            chunks.append(a);cursor+=len(a)
        out.parent.mkdir(parents=True,exist_ok=True);tmp=Path(tempfile.mkdtemp(prefix='.assembly-',dir=out.parent))
        try:
            mixed=np.concatenate(chunks);sf.write(tmp/'narration.wav',mixed,16000,subtype='PCM_16')
            check,_=sf.read(tmp/'narration.wav',dtype='int16')
            for row in timeline:
                source=version(find_sentence(d,row['sentence_id']),row['version_id'])
                samples,_=sf.read(local(root,source['audio']),dtype='int16')
                if not np.array_equal(check[row['start_sample']:row['end_sample']],samples):raise ValueError('Assembly altered sentence samples')
            manifest={'project_id':d['project_id'],'created_at':now(),'sample_rate':16000,'gap_ms':args.gap_ms,'audio_sha256':digest(tmp/'narration.wav'),
                      'sentence_samples_preserved':True,'approved_only':not args.preview,'joins_human_reviewed':False,'timeline':timeline}
            write(tmp/'assembly.json',manifest)
            joins=[]
            for prev,row in zip(timeline,timeline[1:]):
                a=max(0,prev['end_sample']-2*16000);b=min(len(mixed),row['start_sample']+2*16000)
                name='join-'+prev['sentence_id']+'-'+row['sentence_id']+'.wav';sf.write(tmp/name,mixed[a:b],16000,subtype='PCM_16')
                joins.append(f'<p>{prev["sentence_id"]} → {row["sentence_id"]}</p><audio controls preload="none" src="{name}"></audio>')
            label='試聴用：未採用の文を含む場合があります。' if args.preview else '採用版（根拠は各文の記録を参照）。'
            (tmp/'index.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>文単位の結合音声</title><main style="max-width:900px;margin:auto;font-family:sans-serif;line-height:1.8"><h1>文単位の結合音声</h1><p>'+label+'各文の音声サンプルを変更せず結合しています。音量や話し方の統一を保証するものではありません。継ぎ目を聴いて確認してください。</p><audio controls src="narration.wav" style="width:100%"></audio><h2>継ぎ目の確認</h2>'+''.join(joins)+'</main><script>'+player_js()+'</script></html>',encoding='utf-8')
            tmp.rename(out)
        except Exception:shutil.rmtree(tmp);raise
        return {'assembly':str(out),'sentence_samples_preserved':True,'sentences':len(timeline),'duration_s':len(mixed)/16000}


def main(argv=None):
    parser=argparse.ArgumentParser(prog='tts-audit sentences',description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('init');p.add_argument('--script',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--sentences-json',type=Path);p.add_argument('--readings',type=Path)
    p.add_argument('--provider',choices=['external','elevenlabs'],help='Default: external; legacy --voice-id implies elevenlabs')
    p.add_argument('--source-json',type=Path,help='External service/model/voice/settings metadata, without credentials')
    p.add_argument('--model',choices=['eleven_v3','eleven_multilingual_v2']);p.add_argument('--voice-id')
    p.add_argument('--budget-usd',type=float);p.add_argument('--baseline-usd',type=float,default=0);p.add_argument('--max-new-usd',type=float);p.set_defaults(func=init)
    p=sub.add_parser('generate');p.add_argument('project',type=Path);p.add_argument('--sentence',action='append');p.add_argument('--key-file',type=Path,required=True)
    p.add_argument('--regenerate',action='store_true');p.add_argument('--text-file',type=Path);p.add_argument('--max-requests',type=int,default=1);p.set_defaults(func=generate)
    p=sub.add_parser('import-audio');p.add_argument('project',type=Path);p.add_argument('--sentence',required=True);p.add_argument('--audio',type=Path,required=True);p.add_argument('--note',required=True)
    p.add_argument('--text-file',type=Path,help='Actual generation input, separate from canonical text')
    p.add_argument('--source-json',type=Path,help='Actual recording source metadata; otherwise inherit project source');p.set_defaults(func=attach)
    p=sub.add_parser('check');p.add_argument('project',type=Path);p.add_argument('--sentence',action='append');p.add_argument('--version');p.add_argument('--cache-dir',type=Path);p.add_argument('--offline',action='store_true');p.add_argument('--device');p.set_defaults(func=audit)
    p=sub.add_parser('review');p.add_argument('project',type=Path);p.add_argument('--sentence',required=True);p.add_argument('--version');p.add_argument('--verdict',choices=['approved','needs_revision','uncertain'],required=True);p.add_argument('--basis',choices=['human','asr','agent'],required=True);p.add_argument('--note',required=True);p.set_defaults(func=review)
    p=sub.add_parser('select');p.add_argument('project',type=Path);p.add_argument('--sentence',required=True);p.add_argument('--version',required=True);p.set_defaults(func=select)
    p=sub.add_parser('assemble');p.add_argument('project',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--gap-ms',type=float,default=250);p.add_argument('--preview',action='store_true');p.set_defaults(func=assemble)
    p=sub.add_parser('status');p.add_argument('project',type=Path)
    def status(args):
        d=load(args.project.resolve());return {'sentences':[{ 'id':s['id'],'selected':s['selected_version'],'versions':len(s['versions']),'review':(version(s) or {}).get('review')} for s in d['sentences']],'budget':budget(d)}
    p.set_defaults(func=status)
    args=parser.parse_args(argv)
    try:
        result=args.func(args);print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,OSError,ImportError,RuntimeError,KeyError) as e:
        print('tts-audit sentences: '+str(e),file=__import__('sys').stderr);return 1
