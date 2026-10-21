"""A standalone local review page; review labels live in browser storage/export."""
import json
from html import escape as H
from difflib import SequenceMatcher

def diff(a,b):
    left=[];right=[]
    for tag,i,j,k,l in SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        left.append(H(a[i:j]) if tag=='equal' else '<mark>'+H(a[i:j])+'</mark>')
        right.append(H(b[k:l]) if tag=='equal' else '<mark>'+H(b[k:l])+'</mark>')
    return ''.join(left),''.join(right)

def render(data, reviews=None):
    seed = json.dumps((reviews or {}).get('notes', {}), ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    saved_notice = '<p class="box">受け取った聴取記録をこのHTMLにも反映済みです。以後の編集はブラウザー保存です。変更したら再びJSON保存してください。<a href="listening-notes.json">取り込み済みの記録</a>／<a href="review-summary.json">照合結果</a></p>' if reviews else ''
    cards=[];low_cards=[]
    for f in data['findings']:
        a,b=diff(f['expected_kana'],f['observed_kana'])
        status=f.get('boundary_check',{}).get('status')
        label={'not_reproduced':'境界を変えると期待読みと前後の文脈が一致しました。境界依存の差として優先度を下げています。正読確定ではありません。','persistent':'境界を変えても同じ台本箇所に差が残りました。音声で確認してください。','inconclusive':'境界を変えた再認識では判断できませんでした。元の候補を残しています。'}.get(status,'')
        target=low_cards if f.get('review_priority')=='low_boundary' else cards
        target.append(f'''<article data-id="{f['id']}" data-start="{f['start_s']}" data-end="{f['end_s']}"><h2>{f['id']}：{H(f['surface'])}</h2>
        {('<p class="hint">'+H(label)+'</p>') if label else ''}
        <p class="hint">再生区間 {f['start_s']:.1f}–{f['end_s']:.1f}秒（語の正確な時刻ではありません）</p>
        <button class="play">▶ この区間を聴く</button><div class="pair"><div><b>辞書・指定からの期待読み</b><p>{a}</p></div><div><b>カナASR</b><p>{b or '（脱落候補）'}</p></div></div>
        <p>{H(f['reason'])}</p><div class="verdicts"><button data-v="correct">✅ 想定どおり</button><button data-v="error">❌ 読みの違い</button><button data-v="uncertain">🤔 保留</button><button data-v="dictionary">📖 期待読みを修正</button><button data-v="unreviewed">未判定</button></div>
        <label>実際に聞こえた読み <input class="heard" aria-label="聞こえた読み"></label><textarea class="note" placeholder="聴取メモ・対象語外の気付き" aria-label="聴取メモ"></textarea></article>''')
    key='tts-audit-'+data['run_id']
    warnings=''.join('<li>'+H(w['text'])+'：'+H(w['reason'])+'</li>' for w in data['reading_warnings'])
    unavailable='<p class="warn">台本と認識結果の対応が少なく、位置や候補の信頼性が低い可能性があります。原稿違い・無音・未対応語を確認してください。</p>' if data['alignment_equal_fraction']<.5 else ''
    recheck=data.get('boundary_recheck',{})
    recheck_notice='<p class="warn">境界の自動再確認に失敗したため、元の候補をすべて残しています。</p>' if recheck.get('status')=='failed' else ''
    low_section='<details class="box"><summary>境界を変えると消えた差：'+str(len(low_cards))+'件（記録・音声を確認）</summary><p>自動で正読判定や音声修正はしていません。最初のASR結果をそのまま残しています。</p>'+''.join(low_cards)+'</details>' if low_cards else ''
    secondary=recheck.get('secondary_findings',[])
    if secondary:
        recheck_notice+='<p class="warn">切り位置を変えた再認識にも '+str(len(secondary))+'件の差があります。初回とは異なる差もあるため、下の「境界再確認の詳細」で確認してください。</p>'
    diagnostics='<details class="box"><summary>境界再確認の詳細・再認識での差 '+str(len(secondary))+'件</summary><p>切り位置を変え、音声全体をもう一度認識しました。こちらだけで現れた差もあり得るため、自動修正の根拠にはしません。</p><ul>'+''.join('<li>'+H(f['surface'])+'：'+H(f['expected_kana'])+' → '+H(f['observed_kana'])+'</li>' for f in secondary)+'</ul><pre>'+H(json.dumps(recheck,ensure_ascii=False,indent=2))+'</pre></details>' if recheck.get('status')=='completed' else ''
    document=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ナレーションの読み・要確認レポート</title><style>
    body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f2f6f3;color:#263f35;line-height:1.8;margin:0}}main{{max-width:1000px;margin:auto;padding:28px}}h1{{font-size:1.8rem}}h2{{font-size:1.2rem}}article,.box{{background:white;border:1px solid #d0e0d5;border-radius:12px;padding:22px;margin:20px 0}}article.active{{border:2px solid #317856}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}mark{{background:#ffe0a0}}button{{font-size:1rem;padding:9px 13px;margin:4px;border:1px solid #b9cec0;background:#fff;border-radius:8px;cursor:pointer}}button[aria-pressed=true]{{background:#d4eadb;border-color:#217345}}input,textarea{{font:inherit;padding:8px;border:1px solid #b9cec0;border-radius:6px}}input{{max-width:95%}}textarea{{display:block;width:96%;margin-top:12px}}audio{{width:100%}}.hint{{font-size:.9rem;color:#5c7167}}.warn{{background:#fff1d7;padding:12px}}a{{color:#176548}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.sticky{{position:sticky;top:0;background:#f2f6f3;padding:10px 0;z-index:2}}@media(max-width:700px){{main{{padding:15px}}.pair{{grid-template-columns:1fr}}}}
    </style><main><h1>ナレーションの読み・要確認レポート</h1>
    <p>優先して確認する読みの差は <strong>{len(cards)}件</strong>。初回検出 {len(data['findings'])}件のうち、境界再確認で優先度を下げた差は {len(low_cards)}件です。誤読確定ではありません。カナASRの誤認、辞書の誤り、許容される読みも含みます。</p>
    <p class="hint">音声 {data['duration_s']:.1f}秒／{H(data['recognition']['mode'])}／有料API $0。音声の外部送信なし。語の時刻は未推定で、認識区間ごとに再生します。</p>
    <div class="sticky"><audio id="audio" controls preload="metadata" src="audio.wav"></audio><button id="export">聴取記録をJSON保存</button><span id="save">メモはこのブラウザーに保存。共有・バックアップにはJSON保存を使ってください。</span></div>
    {saved_notice}{unavailable}{recheck_notice}<p>区間を選んだ後はスペースで再生・停止できます。入力欄では通常の文字入力になります。</p>
    {''.join(cards) or '<div class="box">優先確認の候補はありません。正読の保証ではありません。全体音声を確認してください。</div>'}
    {low_section}{diagnostics}
    <details class="box"><summary>台本・認識全文・期待読み</summary><h3>台本</h3><pre>{H(data['script'])}</pre><h3>期待読み</h3><pre>{H(data['expected_kana'])}</pre><h3>カナASR</h3><pre>{H(data['observed_kana'])}</pre></details>
    <details class="box"><summary>辞書の読みへの注意・実行条件</summary><ul>{warnings or '<li>文字の未対応警告なし。ただし、辞書読みの正しさを検証済みという意味ではありません。</li>'}</ul><p>長音等を正規化して照合しています。文脈、数字、固有名詞の読みは誤る可能性があります。</p><pre>{H(json.dumps(data['recognition'],ensure_ascii=False,indent=2))}</pre><a href="report.json">機械可読のレポート</a>／<a href="transcript.json">ASR区間</a></details>
    </main><script>
    const key={json.dumps(key)}, runId={json.dumps(data['run_id'])};
    const audio=document.querySelector('#audio'), cards=[...document.querySelectorAll('article')];
    let notes={seed}, active=null, bounded=false;
    try{{const local=JSON.parse(localStorage.getItem(key)||'{{}}');for(const id of Object.keys(local)){{if(cards.some(c=>c.dataset.id===id)&&(!notes[id]||Date.parse(local[id].updated_at)>Date.parse(notes[id].updated_at)))notes[id]=local[id];}}}}catch(e){{document.querySelector('#save').textContent='ブラウザー保存を使えません。JSONで保存してください。'}}
    function save(){{try{{localStorage.setItem(key,JSON.stringify(notes))}}catch(e){{document.querySelector('#save').textContent='保存失敗。JSONで保存してください。'}}}}
    function activate(c){{active=c;cards.forEach(x=>x.classList.toggle('active',x===c));}}
    for(const c of cards){{const id=c.dataset.id, heard=c.querySelector('.heard'), note=c.querySelector('.note');let n=notes[id]||{{verdict:'unreviewed',heard:'',note:''}};
      heard.value=n.heard||'';note.value=n.note||'';
      const refresh=()=>c.querySelectorAll('[data-v]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.v===n.verdict)));
      const update=()=>{{n={{...n,heard:heard.value,note:note.value,updated_at:new Date().toISOString()}};notes[id]=n;save();refresh();}};
      c.querySelectorAll('[data-v]').forEach(b=>b.onclick=()=>{{n.verdict=b.dataset.v;update();}});
      heard.oninput=update;note.oninput=update;c.onpointerdown=()=>activate(c);c.onfocusin=()=>activate(c);
      c.querySelector('.play').onclick=()=>{{activate(c);audio.currentTime=Number(c.dataset.start);bounded=true;audio.play().catch(()=>{{}});}};refresh();
    }}
    audio.addEventListener('timeupdate',()=>{{if(bounded&&active&&audio.currentTime>=Number(active.dataset.end)){{audio.pause();bounded=false;}}}});
    audio.addEventListener('pointerdown',()=>{{bounded=false}});
    document.addEventListener('keydown',e=>{{if(e.code!=='Space'||e.repeat||e.ctrlKey||e.metaKey||e.altKey||e.target.closest('input,textarea,select,[contenteditable=true]'))return;
      e.preventDefault();if(audio.paused){{if(active&&(audio.currentTime<Number(active.dataset.start)||audio.currentTime>=Number(active.dataset.end)))audio.currentTime=Number(active.dataset.start);bounded=!!active;audio.play().catch(()=>{{}});}}else audio.pause();}});
    document.querySelector('#export').onclick=()=>{{const blob=new Blob([JSON.stringify({{schema_version:1,run_id:runId,exported_at:new Date().toISOString(),notes}},null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='tts-audit-listening-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}};
    </script></html>'''
    return document
