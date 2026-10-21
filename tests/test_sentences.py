import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import Mock,patch
import numpy as np
import soundfile as sf
from tts_audit import sentences as s
from tts_audit.core import expected_readings


class SentenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.script=self.base/'script.txt';self.script.write_text('境内を歩く。建立を見る。',encoding='utf-8')
        self.root=self.base/'project'
        self.quiet=contextlib.redirect_stdout(io.StringIO());self.quiet.__enter__();self.addCleanup(self.quiet.__exit__,None,None,None)
        self.init()
        self.counter=0

    def init(self,max_new=1):
        return s.init(NS(out=self.root,script=self.script,sentences_json=None,readings=None,
                         model='eleven_v3',voice_id='testvoice',budget_usd=15.,baseline_usd=14.,max_new_usd=max_new))

    def provider(self,text,d,key):
        self.counter+=1
        raw=io.BytesIO();sf.write(raw,np.full(3200,self.counter*50,dtype='int16'),16000,format='WAV',subtype='PCM_16')
        return raw.getvalue(),{'character_cost':len(text)+1}

    def generate(self,**kwargs):
        args=dict(project=self.root,sentence=None,regenerate=False,text_file=None,max_requests=2,key_file=self.base/'not-read-by-fake')
        args.update(kwargs)
        return s.generate(NS(**args),self.provider)

    def check(self,ids=None,version=None):
        d=s.load(self.root)
        readings=[expected_readings(s.find_sentence(d,i)['canonical_text'])[1] for i in (ids or ['S001','S002'])]
        class Fake:
            def __call__(self,audio):return readings.pop(0)
            def metadata(self):return {'model':'fake-audio-recognizer'}
        with patch('tts_audit.cli.Recognizer',lambda args:Fake()):
            return s.audit(NS(project=self.root,sentence=ids,version=version,cache_dir=None,offline=True,device='cpu'))

    def review(self,ident,verdict='approved',version=None):
        return s.review(NS(project=self.root,sentence=ident,version=version,verdict=verdict,basis='asr',note='Test review, not human hearing'))

    def test_split_preserves_closing_quote_and_manual_text(self):
        self.assertEqual(s.split_sentences('「境内です。」\n次です！'),['「境内です。」','次です！'])
        self.assertEqual(s.split_sentences('値は1.2です。末尾'),['値は1.2です。','末尾'])

    def test_regeneration_retains_approved_audio_until_explicit_selection(self):
        self.generate();self.check();self.review('S001');self.review('S002')
        initial=s.load(self.root);other=json.dumps(initial['sentences'][1],sort_keys=True)
        with self.assertRaises(ValueError):self.generate(sentence=['S001'],regenerate=True,text_file=self.script,max_requests=1)
        self.review('S001','needs_revision')
        fixed=self.base/'fixed.txt';fixed.write_text('けいだいを歩く。',encoding='utf-8')
        self.generate(sentence=['S001'],regenerate=True,text_file=fixed,max_requests=1)
        d=s.load(self.root)
        self.assertEqual(d['sentences'][0]['selected_version'],'v001')
        self.assertEqual(json.dumps(d['sentences'][1],sort_keys=True),other)
        with self.assertRaises(ValueError):s.select(NS(project=self.root,sentence='S001',version='v002'))
        self.check(['S001'],'latest');self.review('S001',version='latest')
        s.select(NS(project=self.root,sentence='S001',version='v002'))
        final=s.load(self.root)
        self.assertEqual(final['sentences'][0]['selected_version'],'v002')
        self.assertEqual(json.dumps(final['sentences'][1],sort_keys=True),other)
        self.assertEqual(len(final['requests']),3)
        self.assertEqual(self.generate()['generated'],[])  # Resume cannot repeat paid generation.

    def test_budget_and_request_limits_prevent_provider_calls(self):
        with self.assertRaises(ValueError):self.generate(max_requests=1)
        self.assertEqual(self.counter,0)
        d=s.load(self.root);d['budget']['max_new_usd']=.0001;s.save(self.root,d)
        with self.assertRaises(ValueError):self.generate()
        self.assertEqual(self.counter,0);self.assertEqual(s.load(self.root)['requests'],[])

    def test_uncertain_request_reservation_blocks_blind_retry(self):
        args=NS(project=self.root,sentence=['S001'],regenerate=False,text_file=None,max_requests=1,key_file=self.base/'unused')
        fail=Mock(side_effect=RuntimeError('unknown network outcome'))
        with self.assertRaises(RuntimeError):s.generate(args,fail)
        d=s.load(self.root);self.assertEqual(d['requests'][0]['outcome'],'uncertain')
        self.assertGreater(s.budget(d)['new_reserved_usd'],0)
        self.assertEqual(d['sentences'][0]['versions'],[])
        with self.assertRaises(ValueError):s.generate(args,fail)
        self.assertEqual(fail.call_count,1)

    def test_tampering_blocks_further_spending(self):
        self.generate();d=s.load(self.root)
        p=self.root/d['sentences'][0]['versions'][0]['audio'];p.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.generate()
        self.assertEqual(self.counter,2)

    def test_assembly_preserves_pcm_and_draft_is_explicit(self):
        self.generate();self.check();self.review('S001');self.review('S002')
        out=self.base/'mix';s.assemble(NS(project=self.root,out=out,gap_ms=250,preview=False))
        manifest=s.read(out/'assembly.json');a,_=sf.read(out/'narration.wav',dtype='int16')
        d=s.load(self.root)
        for row in manifest['timeline']:
            source=s.version(s.find_sentence(d,row['sentence_id']),row['version_id'])
            original,_=sf.read(self.root/source['audio'],dtype='int16')
            np.testing.assert_array_equal(a[row['start_sample']:row['end_sample']],original)
        self.review('S001','needs_revision')
        with self.assertRaises(ValueError):s.assemble(NS(project=self.root,out=self.base/'badmix',gap_ms=250,preview=False))
        s.assemble(NS(project=self.root,out=self.base/'preview',gap_ms=250,preview=True))
        self.assertFalse(s.read(self.base/'preview/assembly.json')['approved_only'])

    def test_checks_skip_unchanged_versions(self):
        self.generate();self.check()
        before=s.read(self.root/'project.json')['sentences']
        with patch('tts_audit.cli.Recognizer',side_effect=AssertionError('should not load ASR')):
            result=s.audit(NS(project=self.root,sentence=None,version=None,cache_dir=None,offline=True,device='cpu'))
            self.assertEqual(result['checked'],[])
        self.assertEqual(before,s.read(self.root/'project.json')['sentences'])

    def test_duplicate_ids_cannot_double_charge(self):
        with self.assertRaises(ValueError):self.generate(sentence=['S001','S001'])
        self.assertEqual(self.counter,0)

    def test_lock_prevents_concurrent_mutation(self):
        with s.locked(self.root):
            with self.assertRaises(ValueError):self.generate()
        self.assertEqual(self.counter,0)

    def test_changed_expectations_invalidate_saved_audits(self):
        self.generate();self.check()
        (self.root/'readings.json').write_text('{"境内":"きょうない"}',encoding='utf-8')
        with self.assertRaises(ValueError):s.load(self.root)

    def test_import_preserves_existing_selected_audio(self):
        self.generate();self.check();self.review('S001')
        before=s.load(self.root)['sentences'][0]
        audio=self.root/before['versions'][0]['audio']
        s.attach(NS(project=self.root,sentence='S001',audio=audio,note='Explicitly imported earlier recording'))
        after=s.load(self.root)['sentences'][0]
        self.assertEqual(after['selected_version'],'v001')
        self.assertEqual(after['versions'][0],before['versions'][0])
        self.assertEqual(after['versions'][1]['provenance']['kind'],'imported')
