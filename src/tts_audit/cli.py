"""Local script + narration -> kana differences and playable review report."""
import argparse
import hashlib
import json
import math
import re
import importlib.metadata
import os
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from . import __version__
from .core import align
from .report import render

MODEL='sbintuitions/kana-whisper'
REVISION='88ecb3d79c5846cb4fcf76f4107b84c8fa2acd82'

def audio_intervals(audio, seconds, rate=16000, first_seconds=None, avoid_boundaries=()):
    """Prefer a nearby quiet boundary instead of cutting a spoken syllable in half."""
    import numpy as np
    start=0;target_size=int(seconds*rate);limit=int(28*rate)
    while start<len(audio):
        if len(audio)-start<=min(target_size+4*rate,limit):
            yield start,len(audio);break
        current_size=int(first_seconds*rate) if start==0 and first_seconds is not None else target_size
        target=start+current_size
        lo=max(start+rate,target-4*rate);hi=min(len(audio)-rate,start+limit,target+4*rate)
        candidates=np.arange(lo,hi+1,320,dtype=int)
        for boundary in avoid_boundaries:
            candidates=candidates[np.abs(candidates-boundary*rate)>=3*rate]
        if not len(candidates) and avoid_boundaries:
            candidates=np.arange(start+rate,min(len(audio)-rate,start+limit)+1,320,dtype=int)
            for boundary in avoid_boundaries:
                candidates=candidates[np.abs(candidates-boundary*rate)>=3*rate]
            if not len(candidates):raise ValueError('Cannot find a shifted boundary; keep the original candidates for review')
        if not len(candidates):end=min(target,len(audio))
        else:
            rms=np.array([np.sqrt(np.mean(audio[max(start,t-800):min(len(audio),t+800)]**2)) for t in candidates])
            scale=max(float(np.max(rms)),1e-5)
            scores=rms+scale*.025*np.abs(candidates-target)/(4*rate)
            end=int(candidates[int(np.argmin(scores))])
        yield start,end;start=end

def load_audio(path):
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    audio,sr=sf.read(str(path),dtype='float32',always_2d=True)
    if len(audio)==0 or not np.isfinite(audio).all():raise ValueError('Audio must contain finite, nonempty samples')
    audio=audio.mean(axis=1)
    if sr!=16000:
        g=math.gcd(sr,16000);audio=resample_poly(audio,16000//g,sr//g).astype(np.float32)
    return audio

def validate_segments(document,duration):
    if not isinstance(document,dict):raise ValueError('Transcript JSON must be an object')
    segments=document.get('segments')
    if not isinstance(segments,list) or not segments:raise ValueError('Transcript JSON needs a nonempty segments array')
    last=0
    for s in segments:
        if not isinstance(s,dict):raise ValueError('Each segment must be an object')
        if not isinstance(s.get('text'),str):raise ValueError('Each segment needs text')
        if re.search(r'[\u3400-\u9fff]',s['text']):raise ValueError('Transcript contains kanji; import kana transcription, not ordinary ASR text')
        start,end=s.get('start_s'),s.get('end_s')
        if not isinstance(start,(float,int)) or not isinstance(end,(float,int)) or not (math.isfinite(start) and math.isfinite(end) and 0<=start<end<=duration+.01 and start>=last-.01):raise ValueError('Invalid, overlapping, or out-of-audio transcript interval')
        if start-last>.1:raise ValueError('Transcript has an unprocessed gap')
        last=end
    if duration-last>.1:raise ValueError('Transcript does not cover the full audio')
    from .core import normalize
    if not any(normalize(s['text'])[0] for s in segments):raise ValueError('No recognized kana; audio is unprocessed, not a clean pass')
    return segments

class Recognizer:
    def __init__(self,args):
        import torch
        from transformers import AutoModelForSpeechSeq2Seq,AutoProcessor,pipeline
        from huggingface_hub import snapshot_download
        self.torch=torch
        self.device=args.device or ('mps' if torch.backends.mps.is_available() else 'cuda:0' if torch.cuda.is_available() else 'cpu')
        self.dtype=torch.float16 if self.device.startswith('cuda') else torch.float32
        print('Loading local Kana Whisper; first download is about 3.24 GB.',flush=True)
        model_path=snapshot_download(MODEL,revision=REVISION,cache_dir=str(args.cache_dir/'hub') if args.cache_dir else None,local_files_only=args.offline,ignore_patterns=['*.bin','*.h5','*.msgpack'])
        model=AutoModelForSpeechSeq2Seq.from_pretrained(model_path,torch_dtype=self.dtype,low_cpu_mem_usage=True,use_safetensors=True,local_files_only=True).to(self.device)
        model.eval();processor=AutoProcessor.from_pretrained(model_path,local_files_only=True)
        self.pipe=pipeline('automatic-speech-recognition',model=model,tokenizer=processor.tokenizer,feature_extractor=processor.feature_extractor,device=self.device,torch_dtype=self.dtype,generate_kwargs={'language':'ja','task':'transcribe'})

    def __call__(self,audio):
        with self.torch.inference_mode():
            return self.pipe({'raw':audio,'sampling_rate':16000})['text']

    def metadata(self):
        return {'model':MODEL,'model_revision':REVISION,'device':self.device,'dtype':str(self.dtype),'torch':self.torch.__version__}


def transcribe(audio,args,recognizer,intervals=None):
    segments=[]
    for start,end in (audio_intervals(audio,args.chunk_seconds) if intervals is None else intervals):
        print(f'Recognizing {start/16000:.1f}–{end/16000:.1f}s',flush=True)
        segments.append({'start_s':start/16000,'end_s':end/16000,'text':recognizer(audio[start:end])})
    return {'segments':segments,'recognition':{'mode':'local Kana Whisper',**recognizer.metadata(),'chunk_seconds':args.chunk_seconds,'chunk_strategy':'nearby_low_energy_v1','script_supplied_to_asr':False,'external_audio_upload':False,'paid_api_cost_usd':0}}


def boundary_recheck(result,audio,args,recognizer=None):
    from .boundaries import reconcile
    times=sorted({b['time_s'] for f in result['findings'] for b in f.get('boundary_context',[])})
    enabled=args.boundary_recheck if args.boundary_recheck is not None else not args.transcript_json
    result['boundary_recheck']={'status':'not_needed' if not times else 'disabled','checks':[]}
    if not times or not enabled:return
    try:
        print('Rechecking boundary-adjacent candidates with independently shifted segments.',flush=True)
        recognizer=recognizer or Recognizer(args)
        intervals=list(audio_intervals(audio,args.chunk_seconds,first_seconds=args.chunk_seconds/2,avoid_boundaries=times))
        second=transcribe(audio,args,recognizer,intervals)
        validate_segments(second,len(audio)/16000)
        compared=align(result['script'],second['segments'],result['readings_override'])
        checks=reconcile(result,compared)
        result['boundary_recheck']={'status':'completed','strategy':'shifted_quiet_full_pass_v1','checks':checks,
            'original_boundary_times_s':times,'minimum_boundary_shift_s':3,
            'segments':second['segments'],'recognition':second['recognition'],
            'alignment_equal_fraction':compared['alignment_equal_fraction'],
            'secondary_findings':compared['findings'],
            'note':'Second-pass-only differences are diagnostic evidence, not confirmed errors. Not reproduced means lower priority, not human-certified correct.'}
    except (ValueError,OSError,ImportError,RuntimeError) as e:
        result['boundary_recheck']={'status':'failed','checks':[],'error_type':type(e).__name__,
            'note':'Automatic recheck failed; keep all original candidates for listening.'}
        print('Boundary recheck failed; original candidates retained.',flush=True)

def check(args,recognizer=None):
    started=time.monotonic()
    if args.out.exists():raise ValueError('Output already exists. Choose a new --out directory to preserve notes and reports.')
    text=args.script.read_text(encoding='utf-8-sig')
    if not text.strip():raise ValueError('Script is empty')
    readings=json.loads(args.readings.read_text()) if args.readings else {}
    if not isinstance(readings,dict):raise ValueError('Readings JSON must be an object')
    audio=load_audio(args.audio);duration=len(audio)/16000
    sha=hashlib.sha256(args.audio.read_bytes()).hexdigest()
    if args.transcript_json:
        transcript=json.loads(args.transcript_json.read_text())
        if not isinstance(transcript,dict):raise ValueError('Transcript JSON must be an object')
        if transcript.get('audio_sha256')!=sha:raise ValueError('Imported transcript audio_sha256 does not match the audio file')
        transcript['recognition']={'mode':'imported kana transcript','source_metadata':transcript.get('recognition',{}),'external_audio_upload':False,'paid_api_cost_usd':0}
    else:
        recognizer=recognizer or Recognizer(args)
        transcript=transcribe(audio,args,recognizer)
    segments=validate_segments(transcript,duration)
    transcript['audio_sha256']=sha
    result=align(text,segments,readings)
    result.update(schema_version=1,version=__version__,run_id=str(uuid.uuid4()),created_at=datetime.now(timezone.utc).isoformat(),script=text,duration_s=duration,audio_sha256=sha,script_sha256=hashlib.sha256(text.encode()).hexdigest(),recognition=transcript['recognition'],segments=segments,readings_override=readings,elapsed_seconds=round(time.monotonic()-started,3),time_note='Segment-level approximate location, not word alignment. Cuts prefer nearby low energy but can still introduce recognition errors.')
    result['dictionary_packages']={name:importlib.metadata.version(name) for name in ('sudachipy','sudachidict_core')}
    boundary_recheck(result,audio,args,recognizer)
    result['elapsed_seconds']=round(time.monotonic()-started,3)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    tmp=Path(tempfile.mkdtemp(prefix='.tts-audit-',dir=args.out.parent))
    try:
        import soundfile as sf
        sf.write(tmp/'audio.wav',audio,16000,subtype='PCM_16')
        (tmp/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        (tmp/'transcript.json').write_text(json.dumps(transcript,ensure_ascii=False,indent=2)+'\n')
        (tmp/'report.html').write_text(render(result))
        tmp.rename(args.out)
    except Exception:
        shutil.rmtree(tmp);raise
    low=sum(f.get('review_priority')=='low_boundary' for f in result['findings'])
    print(json.dumps({'report':str((args.out/'report.html').resolve()),'review_candidates':len(result['findings'])-low,'boundary_deprioritized':low,'reading_warnings':len(result['reading_warnings']),'audio_seconds':duration,'elapsed_seconds':result['elapsed_seconds']},ensure_ascii=False),flush=True)
    return 0

def main(argv=None):
    os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
    os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK','1')
    actual_argv=sys.argv[1:] if argv is None else argv
    if actual_argv and actual_argv[0]=='sentences':
        from .sentences import main as sentence_main
        return sentence_main(actual_argv[1:])
    parser=argparse.ArgumentParser(prog='tts-audit',description='台本と音声から、カナASRに基づく音声付き要確認レポートを作成')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('sentences',help='文単位の生成・点検・版管理・差し替え・結合（sentences --help）')
    p=sub.add_parser('check');p.add_argument('audio',type=Path);p.add_argument('--script',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--readings',type=Path,help='Optional JSON mapping original phrases to expected readings')
    p.add_argument('--transcript-json',type=Path,help='Import complete kana segments bound to the input audio SHA-256')
    p.add_argument('--cache-dir',type=Path);p.add_argument('--offline',action='store_true');p.add_argument('--device');p.add_argument('--chunk-seconds',type=float,default=18)
    p.add_argument('--boundary-recheck',action=argparse.BooleanOptionalAction,default=None,help='Automatically recheck boundary-adjacent differences (default: on for local ASR, off for transcript import)')
    args=parser.parse_args(argv)
    if not 1<=args.chunk_seconds<=28:parser.error('--chunk-seconds must be between 1 and 28')
    try:return check(args)
    except (ValueError,OSError,ImportError,RuntimeError) as e:
        print(f'tts-audit: {e}',file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
