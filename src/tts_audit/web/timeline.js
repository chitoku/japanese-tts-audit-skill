'use strict';
const C=JSON.parse(document.getElementById('config').textContent),R=C.report,$=id=>document.getElementById(id),audio=$('audio');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const duration=R.duration_s, PX=120, storageKey='tts-audit-timeline-'+R.run_id;
const alignment=C.alignment||{script_tokens:[],kana_chars:[],findings:{}};
const audioTimed=alignment.timing_status==='accepted';$('timing-label').textContent=audioTimed?'音声から推定した時刻 · トークン内は按分／厳密な同期は未保証':'台本とASRの照合による位置目安 · 音声との厳密な同期ではありません';$('timing-label').title=alignment.warning||'';
let notes=structuredClone(C.state.notes||{}),annotations=structuredClone(C.state.annotations||[]),revision=C.server?.revision,selected=null,queueFilter='all',zoom=1,peaks=null,segments=[],boundedEnd=null,undoStack=[],dirty=0,persisted=0,saveTimer,saveQueue=Promise.resolve(),savingFailed=false,blocked=false;
let viewTime=0,dragState=null,pendingSeek=null,renderRequest=null,clockUpdated=0;
const queueNodes=new Map();
const tileCache=new Map(),TILE=1024,debug={draws:0,overviewPaints:0,textBuilds:0,tilePaints:0,timings:[]};window.timelineDebug=debug;
let autoFollow=false,followList=[],followStarts=[];
const clamp=t=>Math.max(0,Math.min(duration,t));const clock=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${(t%60).toFixed(1).padStart(4,'0')}`;
const verdictNames={correct:'問題なし',error:'修正が必要',uncertain:'保留',dictionary:'参照読みを確認',unreviewed:'未確認'};
function manualCandidate(a){
 const n=notes[a.id]||{},f={...a,surface:n.target_text||'手動の指摘',reason:'人が追加した指摘です。範囲は追加時刻の前後約3秒の目安です。',manual:true};
 const sel=n.text_selection;if(sel){f.surface=sel.text;f.text_selection=sel;f.reason='人が文字を選択して追加した指摘です。音声の範囲は推定時刻です。';if(sel.source==='script'){f.script_start=sel.start;f.script_end=sel.end;}return f;}
 if(n.target_text){let at=0,best=null;while((at=R.script.indexOf(n.target_text,at))>=0){const end=at+n.target_text.length,tokens=alignment.script_tokens.filter(t=>t.script_start<end&&t.script_end>at);if(tokens.length){const mid=(tokens[0].start_s+tokens.at(-1).end_s)/2,dist=Math.abs(mid-(a.start_s+a.end_s)/2);if(dist<=5&&(!best||dist<best.dist))best={script_start:at,script_end:end,dist,start_s:tokens[0].start_s,end_s:tokens.at(-1).end_s};}at++;}if(best)Object.assign(f,best);}
 return f;
}
const candidates=()=>[...R.findings,...annotations.filter(a=>a.kind==='manual_flag'&&!notes[a.id]?.deleted).map(manualCandidate)].sort((a,b)=>findingSpan(a).start_s-findingSpan(b).start_s||a.id.localeCompare(b.id));
const verdict=f=>notes[f.id]?.verdict||'unreviewed';
const flagLabel=f=>f.manual?'⚑ 手動の指摘':f.review_priority==='low_boundary'?'⋈ 境界の再確認':f.review_priority==='low_variant'||f.expected_reading_uncertain?'▱ 参照読みの確認':!f.observed_kana?'◆ 脱落の可能性':'◆ 読みの不一致';
function renderSessionInfo(){
 const sources=R.source_files||{},base=C.server?.report_directory;
 const rows=[['元の音声ファイル',sources.audio||'元パス未記録（確認用の音声は下記）'],['元の台本ファイル',sources.script||'元パス未記録（台本本文は report.json に保存）'],['確認用音声',C.server?.review_audio_path||'このページと同じフォルダーの audio.wav'],['判定・メモの保存先',C.server?.review_state_path||'このブラウザー内（JSONバックアップで書き出し）'],['解析結果',base?base+'/report.json':'このページと同じフォルダーの report.json'],['セッションID',R.run_id],['作成日時',R.created_at||'未記録'],['保存リビジョン',C.server?String(revision):'—']];
 $('session-fields').replaceChildren();for(const [name,value] of rows){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=value;$('session-fields').append(dt,dd);}
 const name=sources.audio?.split(/[\\/]/).pop()||base?.split(/[\\/]/).pop()||'確認セッション';$('session-short').textContent=name+' · '+String(R.run_id).slice(0,8);$('session-short').title='セッションID: '+R.run_id;
 $('storage-help').textContent=C.server?'ローカルサーバーが判定を自動保存します。エージェントはこの保存先を直接読めます。JSONバックアップの添付は通常不要です。':'ローカルサーバーに接続していません。結果をファイルとして渡すにはJSONバックアップを使ってください。';
 $('export').title=C.server?'任意の控えを書き出します。自動保存とは別で、通常の判定には不要です。':'ブラウザー内の判定をJSONファイルに書き出します。';
}
function saveLabel(){const s=$('save-status');s.classList.toggle('error-text',savingFailed);s.textContent=savingFailed?'保存失敗 · JSONバックアップを作成':dirty>persisted?'保存中…':C.server?'ローカルサーバーへ保存済み':'ブラウザー保存';s.title=C.server?.review_state_path||'ブラウザー内に保存しています';renderSessionInfo();}
function snapshot(){return {notes:structuredClone(notes),annotations:structuredClone(annotations)};}
function pushUndo(){undoStack.push(snapshot());if(undoStack.length>50)undoStack.shift();}
function persist(){
 saveQueue=saveQueue.catch(()=>{}).then(async()=>{if(blocked)throw Error('別の画面で変更されています。JSON保存後に再読込してください。');const serial=dirty,body={schema_version:1,run_id:R.run_id,revision,...snapshot()};const resp=await fetch('api/reviews',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const state=await resp.json();if(!resp.ok){if(resp.status===409)blocked=true;throw Error(state.error||'保存失敗');}revision=state.revision;persisted=serial;savingFailed=false;saveLabel();}).catch(e=>{savingFailed=true;saveLabel();$('notice').textContent=e.message;});return saveQueue;
}
function save(){dirty++;savingFailed=false;try{localStorage.setItem(storageKey,JSON.stringify({...snapshot(),position:audio.currentTime,selectedId:selected?.id}));}catch(e){if(!C.server){savingFailed=true;$('notice').textContent='ブラウザー保存が使えません。JSON保存してください。';}}if(C.server){clearTimeout(saveTimer);saveTimer=setTimeout(persist,250);}else persisted=dirty;saveLabel();}
function touch(id,patch){const old=notes[id]||{};notes[id]={verdict:'unreviewed',heard:'',note:'',...old,...patch,updated_at:new Date(Math.max(Date.now(),(Date.parse(old.updated_at)||0)+1)).toISOString()};save();if(selected)selected=candidates().find(f=>f.id===selected.id)||null;renderCard();renderQueue();renderFlags();refreshVerdicts();updateTextHighlights();rebuildFollowList();}
function chooseVerdict(v){if(!selected)return;pushUndo();touch(selected.id,{verdict:v});$('notice').textContent=autoFollow?'判定を記録しました。再生位置に合わせて次のカードへ進みます。':'判定を記録しました。次へ進むには ↓ または「次の未確認」。';}
function undo(){const prev=undoStack.pop();if(!prev)return;const ids=new Set([...Object.keys(notes),...Object.keys(prev.notes)]);for(const id of ids){const a=notes[id],b=prev.notes[id];if(JSON.stringify(a)!==JSON.stringify(b))prev.notes[id]={verdict:'unreviewed',heard:'',note:'',...b,...(!b&&id.startsWith('M-')?{deleted:true}:{}),updated_at:new Date(Math.max(Date.now(),(Date.parse(a?.updated_at)||0)+1)).toISOString()};}notes=prev.notes;save();renderQueue();select(candidates().find(f=>f.id===selected?.id)||null,false);renderFlags();}
function referenceFor(f){
 if(!f)return '';
 if(!f.manual)return f.observed_kana||'（脱落候補）';
 const selection=notes[f.id]?.text_selection;
 if(selection?.source==='asr')return selection.text;
 const span=findingSpan(f),chars=alignment.kana_chars.filter(c=>c.start_s<span.end_s&&c.end_s>span.start_s);
 return chars.map(c=>c.text).join('')||'該当範囲の認識なし';
}
function refreshVerdicts(){
 document.querySelectorAll('.verdicts button[data-verdict]').forEach(b=>{b.disabled=!selected;b.setAttribute('aria-pressed',String(!!selected&&verdict(selected)===b.dataset.verdict));});
 const manual=!!selected?.manual,n=selected?notes[selected.id]||{}:{};
 for(const [id,value] of [['heard',n.heard||''],['note',n.note||''],['manual-target',manual?n.target_text||'':selected?.surface||''],['manual-expected',manual?n.expected_reading||'':selected?.expected_kana||'']])if(document.activeElement!==$(id))$(id).value=value;
 $('memo-panel').hidden=!selected;$('memo-panel').classList.toggle('is-manual',manual);
 $('manual-target').readOnly=!manual;$('manual-expected').readOnly=!manual;$('expected-label').textContent=manual?'期待する読み（任意）':'台本の参照読み';
 $('delete-manual').hidden=!manual;$('manual-delete-divider').hidden=!manual;
 $('asr-reference').textContent=referenceFor(selected);
}
function focusHeard(){
 $('heard').focus({preventScroll:true});$('heard').select();
}

function context(f){let a=f.script_start,b=f.script_end;if(Number.isInteger(a)&&Number.isInteger(b)&&R.script.slice(a,b)===f.surface){let lo=R.script.lastIndexOf('。',a-1)+1,hi=R.script.indexOf('。',b);if(hi<0)hi=R.script.length;return esc(R.script.slice(lo,a))+'<mark>'+esc(R.script.slice(a,b))+'</mark>'+esc(R.script.slice(b,hi+1));}return esc(f.manual?'気になった音を再生して、修正が必要か確認してください。':R.script.slice(0,100));}
function select(f,seek=true){if(seek)setAutoFollow(false);selected=f;if(f&&seek){audio.pause();boundedEnd=null;setTime(findingSpan(f).start_s-.6);}$('notice').textContent='';renderCard();renderQueue();refreshVerdicts();renderFlags();updateTextHighlights();requestDraw();if(f?.manual&&seek)$('memo-panel').scrollIntoView({block:'nearest'});try{sessionStorage.setItem(storageKey+'-position',JSON.stringify({position:audio.currentTime,selectedId:selected?.id}));}catch(e){} }
function renderCard(){const f=selected;$('card').dataset.verdict=f?verdict(f):'unreviewed';const all=candidates(),i=all.findIndex(x=>x.id===f?.id);$('previous-title').textContent=i>0?all[i-1].surface:'先頭';$('next-title').textContent=i>=0&&i<all.length-1?all[i+1].surface:'最後';$('previous').disabled=i<=0;$('next').disabled=i>=all.length-1||i<0;$('position-label').textContent=f?`${f.id} · 位置目安 ${clock(findingPosition(f))}`:'フラグのない区間を聴く';
 if(!f){$('card').innerHTML='<span class="status-chip">全体をスキャン</span><h1>この位置を、耳で確かめる。</h1><p class="context">機械の指摘がない場所も、正読が保証されたわけではありません。違和感があれば <kbd>M</kbd> を押し、台本かASRの文字を選んで指摘を追加できます。</p><p class="reason">下のタイムラインをクリックして移動。台本・カナASRは詳細から確認できます。</p>';return;}
 $('card').innerHTML=`<span class="status-chip">${esc(flagLabel(f))} · ${esc(verdictNames[verdict(f)])}</span><h1>${esc(f.surface)}</h1><p class="context">${context(f)}</p><p class="reason">${esc(f.reason)} ${f.manual?'':'下の語の位置は文字列照合による概算です。'}</p>`;
}
function highlight(text,term){if(!term)return esc(text);const i=text.indexOf(term);return i<0?esc(text):esc(text.slice(0,i))+'<mark>'+esc(term)+'</mark>'+esc(text.slice(i+term.length));}
function revealQueueSelection(center=false){const q=$('queue'),item=q.querySelector('.selected');if(!item)return;const r=item.getBoundingClientRect(),qr=q.getBoundingClientRect();if(q.scrollHeight>q.clientHeight+1){if(center)q.scrollTop+=r.top-qr.top+(r.height-q.clientHeight)/2;else if(r.top<qr.top)q.scrollTop+=r.top-qr.top;else if(r.bottom>qr.bottom)q.scrollTop+=r.bottom-qr.bottom;}if(q.scrollWidth>q.clientWidth+1){if(center)q.scrollLeft+=r.left-qr.left+(r.width-q.clientWidth)/2;else if(r.left<qr.left)q.scrollLeft+=r.left-qr.left;else if(r.right>qr.right)q.scrollLeft+=r.right-qr.right;}}
function renderQueue(){
 const all=candidates(),pending=all.filter(f=>verdict(f)==='unreviewed'),q=$('queue');
 $('count').textContent=`残り ${pending.length} / ${all.length}`;
 $('progress').style.width=(all.length?100*(all.length-pending.length)/all.length:0)+'%';
 $('pending').textContent=`未確認 ${pending.length}`;
 $('all').textContent=`すべて ${all.length}`;$('errors').textContent=`要修正 ${all.filter(f=>verdict(f)==='error').length}`;
 for(const [id,filter] of [['all','all'],['pending','unreviewed'],['errors','error']])$(id).setAttribute('aria-pressed',String(queueFilter===filter));
 const matches=f=>queueFilter==='all'||verdict(f)===queueFilter;
 const visible=all.filter(f=>matches(f)||f.id===selected?.id),ids=new Set(visible.map(f=>f.id));
 // Retain buttons and their focus/scroll geometry across verdicts and follow changes.
 for(const child of [...q.children])if(!ids.has(child.dataset.id))child.remove();
 let cursor=q.firstElementChild;
 for(const f of visible){
  let b=queueNodes.get(f.id);if(!b){b=document.createElement('button');b.dataset.id=f.id;b.onclick=()=>select(candidates().find(item=>item.id===b.dataset.id));queueNodes.set(f.id,b);}
  b.removeAttribute('aria-pressed');const current=f.id===selected?.id,pinned=current&&!matches(f);
  b.className='queue-item'+(current?' selected':'')+(pinned?' pinned':'');b.dataset.verdict=verdict(f);
  if(f.manual)b.setAttribute('aria-haspopup','menu');else b.removeAttribute('aria-haspopup');
  if(current)b.setAttribute('aria-current','true');else b.removeAttribute('aria-current');
  const signature=JSON.stringify([f.surface,findingPosition(f),verdict(f),pinned]);
  if(b.dataset.signature!==signature){b.dataset.signature=signature;b.innerHTML=`<span class="dot">${verdict(f)==='unreviewed'?'●':verdict(f)==='error'?'✕':verdict(f)==='correct'?'✓':'?'}</span><strong>${esc(f.surface)}</strong><small>目安 ${clock(findingPosition(f))} · ${esc(verdictNames[verdict(f)])}${pinned?' · 現在のカード':''}</small>`;}
  if(b===cursor)cursor=cursor.nextElementSibling;else q.insertBefore(b,cursor);
 }
 if(!visible.length){const e=document.createElement('div');e.className='empty';e.textContent='この条件の候補はありません。';q.append(e);}
 const index=all.findIndex(f=>f.id===selected?.id),pinned=selected&&!matches(selected);
 $('queue-context').textContent=(index>=0?`現在 ${index+1} / ${all.length}`:'カード未選択')+(pinned?' · 条件外の現在カードも表示':queueFilter==='unreviewed'?' · 未確認を表示':queueFilter==='error'?' · 要修正を表示':' · 時刻順');
 revealQueueSelection();
}
function setQueueFilter(filter){
 queueFilter=filter;setAutoFollow(false);
 if(filter!=='all'&&(!selected||verdict(selected)!==filter))select(candidates().find(f=>verdict(f)===filter)||null,false);else renderQueue();
}
function navigate(step,onlyPending=false){const all=candidates();if(!all.length)return;const i=all.findIndex(f=>f.id===selected?.id);if(onlyPending){const next=all.slice(i+1).find(f=>verdict(f)==='unreviewed')||all.find(f=>verdict(f)==='unreviewed');if(next)select(next);}else select(all[Math.max(0,Math.min(all.length-1,i+step))]);}

function findingSpan(f){return alignment.findings[f.id]||{start_s:f.start_s,end_s:f.end_s,focus_s:(f.start_s+f.end_s)/2};}
function findingPosition(f){return clamp(findingSpan(f).focus_s);}
function setTime(t,commit=true){viewTime=clamp(t);boundedEnd=null;if(commit){if(audio.readyState>=1)audio.currentTime=viewTime;else pendingSeek=viewTime;}requestDraw();}
function seek(t){setAutoFollow(false);setTime(t);}
function play(){if(audio.paused){if(Math.abs(audio.currentTime-viewTime)>.05&&audio.readyState>=1)audio.currentTime=viewTime;audio.play().catch(()=>{$('notice').textContent='音声を再生できません。音声ファイルの読み込みを確認してください。';});}else audio.pause();}
function replay(){setAutoFollow(false);if(!selected){play();return;}const span=findingSpan(selected);setTime(span.start_s-1);boundedEnd=clamp(Math.max(span.end_s,span.start_s+.3)+1);audio.play().catch(()=>{$('notice').textContent='音声を再生できません。';});}

let textSelectionMode=false,pendingTextSelection=null,selectionAnchor=null;
const selectionOverlay=document.createElement('div');selectionOverlay.id='selection-rainbow';selectionOverlay.setAttribute('aria-hidden','true');$('detail').append(selectionOverlay);
function resetTextSelectionPreview(){pendingTextSelection=null;$('detail').classList.remove('is-selecting-text');selectionOverlay.replaceChildren();}
function paintSelectedText(source,start,end){
 const area=$('detail').getBoundingClientRect(),rects=[];
 for(const token of document.querySelectorAll(source==='script'?'#script-track .text-token':'#kana-track .asr-glyph')){
  const a=Number(token.dataset.textStart),b=Number(token.dataset.textEnd);if(a>=end||b<=start)continue;
  if(source==='asr')rects.push(token.getBoundingClientRect());else{let offset=a;for(const glyph of token.children){const next=offset+glyph.textContent.length;if(offset<end&&next>start)rects.push(glyph.getBoundingClientRect());offset=next;}}
 }

 // Native ranges may report both a token and its text; union overlaps per line.
 const bands=[];for(const r of rects.sort((a,b)=>a.top-b.top||a.left-b.left)){const last=bands[bands.length-1];if(last&&Math.abs(last.top-r.top)<2){last.right=Math.max(last.right,r.right);last.bottom=Math.max(last.bottom,r.bottom);}else bands.push({left:r.left,right:r.right,top:r.top,bottom:r.bottom});}
 const fragment=document.createDocumentFragment();for(const r of bands){const band=document.createElement('div');band.className='selection-rainbow-band';band.style.left=(r.left-area.left-$('detail').clientLeft)+'px';band.style.top=(r.top-area.top-$('detail').clientTop)+'px';band.style.width=(r.right-r.left)+'px';band.style.height=(r.bottom-r.top)+'px';fragment.append(band);}
 selectionOverlay.replaceChildren(fragment);$('detail').classList.toggle('is-selecting-text',bands.length>0);
}
function clearTextSelection(){selectionAnchor=null;resetTextSelectionPreview();window.getSelection()?.removeAllRanges();}
function setTextSelectionMode(on){textSelectionMode=on;if(on)audio.pause();setAutoFollow(false);$('detail').classList.toggle('text-selection-mode',on);$('text-select').setAttribute('aria-pressed',String(on));$('text-select').innerHTML=on?'台本またはASRの文字を選んでください <kbd>Esc</kbd>':'文字選択して手動指摘 <kbd>M</kbd>';$('text-select').title=on?'文字を選択して離すと追加。クリック・M・Escでキャンセル':'台本またはASRの文字を選択し、離すと指摘を追加';clearTextSelection();}
function captureTextSelection(){
 if(!textSelectionMode)return;const sel=window.getSelection();if(!sel||sel.isCollapsed){resetTextSelectionPreview();return;}
 const point=(node,offset)=>{const element=(node.nodeType===Node.ELEMENT_NODE?node:node.parentElement).closest('.text-token,.asr-glyph');if(!element)return null;const track=element.closest('#script-track,#kana-track');if(!track)return null;const range=document.createRange();range.selectNodeContents(element);try{range.setEnd(node,offset)}catch(e){return null;}return {source:track.id==='script-track'?'script':'asr',position:Number(element.dataset.textStart)+range.toString().length};};
 const a=point(sel.anchorNode,sel.anchorOffset),b=point(sel.focusNode,sel.focusOffset);if(!a||!b||a.source!==b.source||a.position===b.position){resetTextSelectionPreview();return;}
 const source=a.source,anchor=selectionAnchor?.source===source?selectionAnchor:null,start=Math.min(a.position,b.position,anchor?.start??Infinity),end=Math.max(a.position,b.position,anchor?.end??-Infinity),text=(source==='script'?R.script:R.observed_kana).slice(start,end);if(!text.trim()){resetTextSelectionPreview();return;}
 const nodes=[...document.querySelectorAll(source==='script'?'#script-track .text-token':'#kana-track .asr-glyph')].filter(e=>Number(e.dataset.textStart)<end&&Number(e.dataset.textEnd)>start);if(!nodes.length){resetTextSelectionPreview();return;}
 pendingTextSelection={source,start,end,text,start_s:Math.min(...nodes.map(e=>Number(e.dataset.startS))),end_s:Math.max(...nodes.map(e=>Number(e.dataset.endS)))};
 paintSelectedText(source,start,end);

}
function flagSelectedText(){
 if(!pendingTextSelection)return;const s={...pendingTextSelection};const uid=crypto.randomUUID?.()||Date.now().toString(36);const a=clamp(s.start_s),b=clamp(Math.max(s.end_s,a+.1));if(b<=a)return;pushUndo();const id='M-'+uid;
 annotations.push({id,kind:'manual_flag',start_s:a,end_s:b,created_at:new Date().toISOString()});notes[id]={verdict:'error',heard:s.source==='asr'?s.text:'',note:'',target_text:s.source==='script'?s.text:'',text_selection:{source:s.source,start:s.start,end:s.end,text:s.text},updated_at:new Date().toISOString()};
 clearTextSelection();setTextSelectionMode(false);save();select(candidates().find(f=>f.id===id),false);$('memo-panel').scrollIntoView({block:'nearest'});focusHeard();$('notice').textContent='実際に聞こえた読みを入力できます。Escで判定キーへ戻れます。';
}
$('text-select').onclick=()=>setTextSelectionMode(!textSelectionMode);
$('detail').addEventListener('pointerdown',e=>{
 if(!textSelectionMode)return;selectionAnchor=null;
 const glyph=e.target.closest('.asr-glyph,#script-track .text-token>span');if(!glyph)return;
 const token=glyph.closest('.text-token,.asr-glyph'),source=token.classList.contains('asr-glyph')?'asr':'script';let start=Number(token.dataset.textStart);
 if(source==='script')for(const sibling of token.children){if(sibling===glyph)break;start+=sibling.textContent.length;}
 selectionAnchor={source,start,end:start+glyph.textContent.length};
});

let selectionFrame=null;
document.addEventListener('selectionchange',()=>{if(selectionFrame!==null)return;selectionFrame=requestAnimationFrame(()=>{selectionFrame=null;captureTextSelection()})});
// Commit only when the gesture ends: selectionchange also fires while dragging.
function finishTextSelection(){if(!textSelectionMode)return;captureTextSelection();flagSelectedText();}
document.addEventListener('pointerup',()=>{if(textSelectionMode)setTimeout(finishTextSelection,0)});
document.addEventListener('keyup',e=>{if(e.key==='Shift'&&textSelectionMode)finishTextSelection()});
function manual(){setTextSelectionMode(!textSelectionMode);}
function deleteManual(id=selected?.id){const all=candidates(),index=all.findIndex(f=>f.id===id),victim=all[index];if(!victim?.manual)return;const wasSelected=selected?.id===id;pushUndo();touch(id,{deleted:true});if(wasSelected){const remaining=candidates();select(remaining[Math.min(index,remaining.length-1)]||null,false);}$('notice').textContent='手動の指摘を削除しました。「取り消す」で戻せます。';}
let queueMenuTarget=null,queueMenuOrigin=null;
function closeQueueMenu(restoreFocus=false){$('queue-menu').hidden=true;queueMenuTarget=null;if(restoreFocus&&queueMenuOrigin?.isConnected)queueMenuOrigin.focus();queueMenuOrigin=null;}
function openQueueMenu(row,x,y){const f=candidates().find(item=>item.id===row.dataset.id);if(!f?.manual)return false;setAutoFollow(false);queueMenuTarget=f.id;queueMenuOrigin=row;const menu=$('queue-menu');$('queue-menu-label').textContent=f.surface+' · '+clock(findingPosition(f));menu.hidden=false;menu.style.left='0px';menu.style.top='0px';const rect=menu.getBoundingClientRect();menu.style.left=Math.max(8,Math.min(x,innerWidth-rect.width-8))+'px';menu.style.top=Math.max(8,Math.min(y,innerHeight-rect.height-8))+'px';$('queue-menu-delete').focus();return true;}
$('queue').addEventListener('contextmenu',e=>{const row=e.target.closest('.queue-item');if(!row)return;if(openQueueMenu(row,e.clientX||row.getBoundingClientRect().left,e.clientY||row.getBoundingClientRect().bottom)){e.preventDefault();e.stopPropagation();}});
$('queue').addEventListener('keydown',e=>{if(e.key!=='ContextMenu'&&!(e.shiftKey&&e.key==='F10'))return;const row=e.target.closest('.queue-item');if(row&&openQueueMenu(row,row.getBoundingClientRect().left,row.getBoundingClientRect().bottom))e.preventDefault();});
$('queue-menu-delete').onclick=()=>{const id=queueMenuTarget;closeQueueMenu();deleteManual(id)};
document.addEventListener('pointerdown',e=>{if(!$('queue-menu').hidden&&!e.target.closest('#queue-menu'))closeQueueMenu()});window.addEventListener('resize',()=>closeQueueMenu());document.addEventListener('scroll',()=>closeQueueMenu(),true);

function visibleRange(){const half=$('detail').clientWidth/PX/2;return [clamp(viewTime-half),clamp(viewTime+half)];}
function scan(){const [a,b]=visibleRange();if(b<=a)return;annotations.push({id:'S-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2),kind:'reviewed_range',start_s:a,end_s:b,created_at:new Date().toISOString()});save();renderCoverage();paintOverview();requestDraw();$('notice').textContent=`${clock(a)}–${clock(b)} を人が確認済みとして記録しました。候補の判定とは別の記録です。`;}
function canvas(id){const c=$(id),w=c.clientWidth,h=c.clientHeight,dpr=Math.min(devicePixelRatio||1,16384/Math.max(1,w));if(c.width!==Math.round(w*dpr)||c.height!==Math.round(h*dpr)){c.width=Math.round(w*dpr);c.height=Math.round(h*dpr);}const x=c.getContext('2d');x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,w,h);return {x,w,h};}
let wavePalette={};const themeMedia=matchMedia('(prefers-color-scheme: dark)');let themePreference='auto';try{const t=localStorage.getItem('tts-audit-theme');if(['auto','light','dark'].includes(t))themePreference=t;}catch(e){}
function applyTheme(preference,persist=false){
 themePreference=['auto','light','dark'].includes(preference)?preference:'auto';document.documentElement.dataset.theme=themePreference==='auto'?(themeMedia.matches?'dark':'light'):themePreference;$('theme').value=themePreference;
 if(persist)try{localStorage.setItem('tts-audit-theme',themePreference)}catch(e){}
 const style=getComputedStyle(document.documentElement);for(const key of ['grid','label','detail','overview'])wavePalette[key]=style.getPropertyValue('--wave-'+key).trim();wavePalette.coverage=style.getPropertyValue('--ok').trim();
 for(const tile of tileCache.values())tile.remove();tileCache.clear();if(peaks){paintOverview();requestDraw();}
}
$('theme').onchange=()=>applyTheme($('theme').value,true);themeMedia.addEventListener('change',()=>{if(themePreference==='auto')applyTheme('auto')});window.addEventListener('storage',e=>{if(e.key==='tts-audit-theme')applyTheme(e.newValue)});applyTheme(themePreference);
function rasterWave(x,w,h,start,end,detail=false){const scale=w/(end-start);x.strokeStyle=wavePalette.grid;x.fillStyle=wavePalette.label;x.font='10px monospace';const tick=detail?1:Math.max(1,Math.ceil((end-start)/10));for(let t=Math.max(0,Math.ceil(start/tick)*tick);t<=Math.min(duration,end);t+=tick){const z=(t-start)*scale;x.beginPath();x.moveTo(z,17);x.lineTo(z,h-5);x.stroke();x.fillText(clock(t),z+4,11);}if(!peaks)return;x.fillStyle=detail?wavePalette.detail:wavePalette.overview;for(let i=0;i<w;i+=2){const t=start+i/scale;if(t<0||t>=duration)continue;const p=peaks[Math.min(peaks.length-1,Math.floor(t/duration*peaks.length))]||0;const a=Math.max(1,p*(h-24)*.43);x.fillRect(i,17+(h-24)/2-a,1.4,a*2);}}
function paintOverview(){debug.overviewPaints++;const {x,w,h}=canvas('overview-wave');rasterWave(x,w,h,0,duration);for(const a of annotations.filter(a=>a.kind==='reviewed_range')){x.fillStyle=wavePalette.coverage;x.fillRect(a.start_s/duration*w,h-4,(a.end_s-a.start_s)/duration*w,3);}}
function ensureTiles(t){if(!peaks)return;const half=$('detail').clientWidth/2;const lo=Math.max(0,Math.floor((t*PX-half)/TILE)-1),hi=Math.min(Math.ceil(duration*PX/TILE)-1,Math.floor((t*PX+half)/TILE)+1);for(let i=lo;i<=hi;i++){if(tileCache.has(i))continue;const c=document.createElement('canvas'),dpr=Math.min(devicePixelRatio||1,2);c.className='wave-tile';c.width=TILE*dpr;c.height=71*dpr;c.style.left=i*TILE+'px';const x=c.getContext('2d');x.scale(dpr,dpr);rasterWave(x,TILE,71,i*TILE/PX,(i+1)*TILE/PX,true);$('wave-tiles').append(c);tileCache.set(i,c);debug.tilePaints++;}while(tileCache.size>32){const remove=[...tileCache.keys()].find(k=>k<lo||k>hi);if(remove===undefined)break;tileCache.get(remove).remove();tileCache.delete(remove);}}
function buildTextTracks(){debug.textBuilds++;$('detail-world').style.width=duration*PX+'px';for(const [track,items,script] of [['script-track',alignment.script_tokens,true],['kana-track',alignment.kana_chars,false]]){const fragment=document.createDocumentFragment();let textOffset=0;for(const item of items){const node=document.createElement('span');node.className=script?'text-token':'asr-glyph';node.style.left=item.start_s*PX+'px';const width=Math.max(1,(item.end_s-item.start_s)*PX);node.style.width=width+'px';node.dataset.baseFindingIds=JSON.stringify(item.finding_ids||[]);node.dataset.findingIds=node.dataset.baseFindingIds;node.dataset.textStart=script?item.script_start:textOffset;node.dataset.textEnd=script?item.script_end:textOffset+item.text.length;textOffset+=item.text.length;node.dataset.startS=item.start_s;node.dataset.endS=item.end_s;if(script){node.dataset.scriptStart=item.script_start;node.dataset.scriptEnd=item.script_end;}node.title=audioTimed?'Kana Whisperの音声注意・DTWによる推定時刻（トークン内は按分）':'文字列照合と認識区間内の按分による位置目安';if(script){const chars=Array.from(item.text);for(const ch of chars){const glyph=document.createElement('span');glyph.style.width=(100/chars.length)+'%';glyph.textContent=ch;node.append(glyph);}}else node.textContent=item.text;if(item.finding_ids?.length){node.classList.add('has-diff');node.title+=' · '+item.finding_ids.join(', ');}fragment.append(node);}$(track).replaceChildren(fragment);}updateTextHighlights();renderCoverage();}
function updateTextHighlights(){const manual=candidates().filter(f=>f.manual&&(f.script_start!==undefined||f.text_selection));document.querySelectorAll('[data-finding-ids]').forEach(e=>{const ids=JSON.parse(e.dataset.baseFindingIds||'[]');for(const f of manual){const hit=f.text_selection?.source==='asr'?(e.dataset.scriptStart===undefined&&Number(e.dataset.textStart)<f.text_selection.end&&Number(e.dataset.textEnd)>f.text_selection.start):e.dataset.scriptStart!==undefined?Number(e.dataset.scriptStart)<f.script_end&&Number(e.dataset.scriptEnd)>f.script_start:Number(e.dataset.startS)<f.end_s&&Number(e.dataset.endS)>f.start_s;if(hit)ids.push(f.id);}e.dataset.findingIds=JSON.stringify(ids);e.classList.toggle('has-diff',ids.length>0);e.classList.toggle('is-selected',!!selected&&ids.includes(selected.id));const states=ids.map(id=>notes[id]?.verdict||'unreviewed');e.dataset.verdict=states.includes('error')?'error':states.length&&states.every(v=>v==='correct')?'correct':states.includes('uncertain')?'uncertain':'unreviewed';});}
function rebuildFollowList(){followList=candidates().sort((a,b)=>findingSpan(a).start_s-findingSpan(b).start_s||a.id.localeCompare(b.id));followStarts=followList.map(f=>findingSpan(f).start_s);}
function setAutoFollow(on,alignNow=true){autoFollow=!!on;$('auto-follow').setAttribute('aria-pressed',String(autoFollow));$('auto-follow').innerHTML=(autoFollow?'自動追従 ON':'自動追従 OFF')+' <kbd>F</kbd>';try{localStorage.setItem(storageKey+'-follow',String(autoFollow))}catch(e){}if(autoFollow){rebuildFollowList();if(alignNow)followPlayback(true);}}
function followPlayback(force=false){if(!autoFollow||dragState||(!force&&audio.paused)||document.activeElement?.closest('#memo-panel input,#memo-panel textarea,#manual-editor input'))return;if(!followList.length)return;const t=audio.currentTime+.2;let lo=0,hi=followStarts.length;while(lo<hi){const mid=(lo+hi)>>1;if(followStarts[mid]<=t)lo=mid+1;else hi=mid;}const target=followList[Math.max(0,lo-1)];if(target&&target.id!==selected?.id){select(target,false);revealQueueSelection(true);}}

function renderCoverage(){const frag=document.createDocumentFragment();for(const a of annotations.filter(a=>a.kind==='reviewed_range')){const e=document.createElement('div');e.className='coverage-range';e.style.left=a.start_s*PX+'px';e.style.width=(a.end_s-a.start_s)*PX+'px';frag.append(e);}$('detail-coverage').replaceChildren(frag);}
function requestDraw(){if(renderRequest!==null)return;renderRequest=requestAnimationFrame(()=>{renderRequest=null;draw();});}
function draw(){const began=performance.now(),t=viewTime,w=$('detail').clientWidth;ensureTiles(t);$('detail-world').style.transform=`translate3d(${w/2-t*PX}px,0,0)`;if(began-clockUpdated>50){$('clock').textContent=`${clock(t)} / ${clock(duration)}`;clockUpdated=began;}$('detail').setAttribute('aria-valuenow',t.toFixed(1));$('detail').setAttribute('aria-valuemax',duration);const total=$('overview-inner').clientWidth;$('overview-playhead').style.transform=`translate3d(${t/duration*total}px,0,0)`;const [a,b]=visibleRange();$('focus-window').style.transform=`translate3d(${a/duration*total}px,0,0)`;$('focus-window').style.width=(b-a)/duration*total+'px';$('focus-window').setAttribute('aria-valuenow',t.toFixed(1));$('focus-window').setAttribute('aria-valuemax',duration);debug.draws++;debug.timings.push(performance.now()-began);if(debug.timings.length>600)debug.timings.shift();}
function layoutOverview(){const w=$('overview-scroll').clientWidth*zoom;$('overview-inner').style.width=w+'px';$('zoom-label').textContent=zoom===1?'全体':zoom+'×';$('scene-strip').replaceChildren();for(const s of segments){const el=document.createElement('div');el.className='scene-tile';el.style.left=s.start_s/duration*w+'px';el.style.width=(s.end_s-s.start_s)/duration*w+'px';el.innerHTML=`${clock(s.start_s)}<small>${esc(s.text)}</small>`;$('scene-strip').append(el);}renderFlags();paintOverview();requestDraw();}
function renderDetailManualFlags(){
 const fragment=document.createDocumentFragment();
 candidates().filter(f=>f.manual).forEach((f,i)=>{
  const span=findingSpan(f),band=document.createElement('div');band.className='detail-manual-flag'+(selected?.id===f.id?' is-current':'');band.dataset.id=f.id;band.dataset.verdict=verdict(f);band.style.left=span.start_s*PX+'px';band.style.width=Math.max(8,(span.end_s-span.start_s)*PX)+'px';
  const button=document.createElement('button');button.className='manual-flag-label';button.style.top=(4+i%3*18)+'px';button.textContent='⚑ '+f.surface;button.title=`${f.surface} · ${clock(span.start_s)}–${clock(span.end_s)} · ${verdictNames[verdict(f)]}（手動の位置目安）`;button.setAttribute('aria-label',button.title);button.setAttribute('aria-pressed',String(selected?.id===f.id));button.onpointerdown=e=>e.stopPropagation();button.onclick=e=>{e.stopPropagation();select(f)};band.append(button);fragment.append(band);
 });
 $('detail-manual-flags').replaceChildren(fragment);
}
function renderFlags(){renderDetailManualFlags();const w=$('overview-inner').clientWidth;$('flag-track').replaceChildren();for(const f of candidates()){const span=findingSpan(f),el=document.createElement('div');el.className='flag'+(f.manual?' manual':'');el.dataset.verdict=verdict(f);if(f.id===selected?.id)el.classList.add('selected-flag');el.style.left=span.start_s/duration*w+'px';el.style.width=Math.max(4,(span.end_s-span.start_s)/duration*w)+'px';el.title=`${f.surface} · ${verdictNames[verdict(f)]} · 文字照合による位置目安`;el.setAttribute('role','button');el.tabIndex=0;el.setAttribute('aria-label',el.title);el.innerHTML=`<span>${esc(f.surface)}</span>`;el.onclick=e=>{e.stopPropagation();select(f)};el.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();select(f)}};$('flag-track').append(el);}}

async function loadMedia(){try{const [raw,trans]=await Promise.all([fetch('audio.wav').then(r=>{if(!r.ok)throw Error('音声の読み込みに失敗');return r.arrayBuffer()}),Object.keys(C.transcript).length?Promise.resolve(C.transcript):fetch('transcript.json').then(r=>r.ok?r.json():{})]);segments=trans.segments||[];buildTextTracks();const ctx=new (window.AudioContext||window.webkitAudioContext)();let decoded;try{decoded=await ctx.decodeAudioData(raw)}finally{await ctx.close()}const bins=Math.min(100000,Math.max(1000,Math.ceil(duration*100))),channels=Array.from({length:decoded.numberOfChannels},(_,i)=>decoded.getChannelData(i));peaks=new Float32Array(bins);for(let i=0;i<bins;i++){const a=Math.floor(i*decoded.length/bins),b=Math.floor((i+1)*decoded.length/bins);let max=0;for(const channel of channels)for(let j=a;j<b;j++)max=Math.max(max,Math.abs(channel[j]));peaks[i]=max;}layoutOverview();}catch(e){$('notice').textContent='波形を表示できません。再生と判定は引き続き利用できます。';$('notice').title=e.message;}}
// Server data is authoritative. Browser recovery never overwrites it silently.
let restored=null;try{restored=JSON.parse(sessionStorage.getItem(storageKey+'-position')||'null');if(!C.server){const local=JSON.parse(localStorage.getItem(storageKey)||'null');if(local){notes=local.notes||notes;annotations=local.annotations||annotations;restored=restored||local;}}}catch(e){}
function setEvidenceLayout(value){const layout=value==='stacked'?'stacked':'side';$('evidence-layout').value=layout;$('memo-panel').classList.toggle('is-stacked',layout==='stacked');try{localStorage.setItem('tts-audit-evidence-layout',layout)}catch(e){}}
$('evidence-layout').onchange=()=>setEvidenceLayout($('evidence-layout').value);try{setEvidenceLayout(localStorage.getItem('tts-audit-evidence-layout'))}catch(e){setEvidenceLayout('side')}
$('delete-manual').onclick=()=>deleteManual();for(const [id,field] of [['manual-target','target_text'],['manual-expected','expected_reading']])$(id).oninput=()=>{if(selected?.manual)touch(selected.id,{[field]:$(id).value,...(field==='target_text'?{text_selection:null}:{})})};$('full-script').textContent=R.script;$('full-transcript').textContent=R.observed_kana;$('auto-follow').onclick=()=>setAutoFollow(!autoFollow);$('full-scan').onclick=()=>{setAutoFollow(false);select(null,false);};$('play').onclick=play;$('replay').onclick=replay;$('scan').onclick=scan;$('undo').onclick=undo;$('speed').onchange=()=>audio.playbackRate=Number($('speed').value);$('previous').title='前の指摘（↑）';$('next').title='次の指摘・判定済みも含む（Shift＋↓）';$('previous').onclick=()=>navigate(-1);$('next').onclick=()=>navigate(1);$('next-pending').onclick=()=>navigate(1,true);$('all').onclick=()=>setQueueFilter('all');$('pending').onclick=()=>setQueueFilter('unreviewed');$('errors').onclick=()=>setQueueFilter('error');document.querySelectorAll('.verdicts button[data-verdict]').forEach(b=>b.onclick=()=>chooseVerdict(b.dataset.verdict));$('heard').oninput=()=>{if(selected)touch(selected.id,{heard:$('heard').value})};$('note').oninput=()=>{if(selected)touch(selected.id,{note:$('note').value})};
// Coalesce pointer moves to one display update per animation frame. Media seeks
// happen on release, rather than forcing the decoder to seek for every pixel.
function beginDrag(e,kind){if(e.button!==0)return;if(kind==='detail'&&textSelectionMode&&e.target.closest('#script-track,#kana-track'))return;setAutoFollow(false);if(e.target.closest('.flag'))return;const area=e.currentTarget,windowDrag=kind==='overview'&&!!e.target.closest('#focus-window');dragState={kind,area,id:e.pointerId,x:e.clientX,time:viewTime,moved:false,windowDrag,findingIds:JSON.parse(e.target.closest('[data-finding-ids]')?.dataset.findingIds||'[]'),wasPlaying:!audio.paused};audio.pause();area.setPointerCapture(e.pointerId);area.classList.add('dragging');$('focus-window').classList.toggle('dragging',windowDrag);}
function moveDrag(e){if(!dragState||e.pointerId!==dragState.id)return;const dx=e.clientX-dragState.x;if(Math.abs(dx)>2)dragState.moved=true;let t;if(dragState.kind==='detail')t=dragState.time-dx/PX;else if(dragState.windowDrag)t=dragState.time+dx/$('overview-inner').clientWidth*duration;else t=(e.clientX-$('overview-inner').getBoundingClientRect().left)/$('overview-inner').clientWidth*duration;setTime(t,false);}
function endDrag(e,cancel=false){if(!dragState||e.pointerId!==dragState.id)return;const d=dragState;dragState=null;d.area.classList.remove('dragging');$('focus-window').classList.remove('dragging');if(!cancel&&!d.moved){if(d.kind==='detail'){const ids=d.findingIds;if(ids.length){select(candidates().find(f=>f.id===ids[0]));}else setTime(d.time+(e.clientX-$('detail').getBoundingClientRect().left-$('detail').clientWidth/2)/PX);}else if(!d.windowDrag)setTime((e.clientX-$('overview-inner').getBoundingClientRect().left)/$('overview-inner').clientWidth*duration);}if(cancel)setTime(d.time);else setTime(viewTime);if(d.wasPlaying&&!cancel)audio.play().catch(()=>{});}
for(const [id,kind] of [['detail','detail'],['overview-inner','overview']]){const area=$(id);area.addEventListener('pointerdown',e=>beginDrag(e,kind));area.addEventListener('pointermove',moveDrag);area.addEventListener('pointerup',e=>endDrag(e));area.addEventListener('pointercancel',e=>endDrag(e,true));area.addEventListener('lostpointercapture',e=>{if(dragState?.id===e.pointerId)endDrag(e,true)});}
$('detail').addEventListener('click',e=>{if(textSelectionMode||e.target.closest('[data-finding-ids]'))return;e.preventDefault();});
$('detail').addEventListener('wheel',e=>{e.preventDefault();setAutoFollow(false);setTime(viewTime+(e.deltaY+e.deltaX)/PX)},{passive:false});

function changeZoom(v){const anchor=viewTime/duration;zoom=v;layoutOverview();$('overview-scroll').scrollLeft=Math.max(0,anchor*$('overview-inner').clientWidth-$('overview-scroll').clientWidth/2);}
$('zoom-in').onclick=()=>changeZoom(Math.min(16,zoom*2));$('zoom-out').onclick=()=>changeZoom(Math.max(1,zoom/2));$('fit').onclick=()=>changeZoom(1);
$('export').onclick=()=>{const data={schema_version:1,run_id:R.run_id,exported_at:new Date().toISOString(),...snapshot()};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='tts-audit-listening-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
$('shortcut-help').onclick=()=>$('shortcut-dialog').showModal();$('close-shortcuts').onclick=()=>$('shortcut-dialog').close();
function pulseShortcut(selector){
 const button=document.querySelector(selector);if(!button||button.disabled)return;
 button.classList.remove('shortcut-pulse');void button.offsetWidth;button.classList.add('shortcut-pulse');
 button.addEventListener('animationend',()=>button.classList.remove('shortcut-pulse'),{once:true});
}
const shortcutButtons={Space:'#play',ArrowUp:'#previous',Digit1:'.verdicts [data-verdict=correct]',Digit2:'.verdicts [data-verdict=error]',Digit3:'.verdicts [data-verdict=uncertain]',KeyF:'#auto-follow',KeyM:'#text-select',KeyR:'#replay',KeyA:'#full-scan',Equal:'#zoom-in',NumpadAdd:'#zoom-in',Minus:'#zoom-out',NumpadSubtract:'#zoom-out',Digit0:'#fit'};
window.addEventListener('keydown',e=>{
 if(e.target===$('note')&&e.key==='Tab'&&!e.shiftKey&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!e.isComposing){e.preventDefault();$('detail').focus({preventScroll:true});return;}
 if(textSelectionMode&&e.key==='Escape'){e.preventDefault();setTextSelectionMode(false);pulseShortcut('#text-select');return;}
 if(e.target.closest('#memo-panel input,#memo-panel textarea')&&e.key==='Escape'&&!e.isComposing){e.preventDefault();e.target.blur();$('detail').focus({preventScroll:true});return;}
 if(e.target.closest('input,textarea,select,summary,[contenteditable=true]')||e.repeat)return;
 if(!$('queue-menu').hidden){if(e.key==='Escape'){e.preventDefault();closeQueueMenu(true);}else if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();$('queue-menu-delete').focus();}return;}
 if($('shortcut-dialog').open)return;
 if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='z'){e.preventDefault();undo();pulseShortcut('#undo');return;}
 if(e.metaKey||e.ctrlKey||e.altKey)return;
 if(textSelectionMode&&e.shiftKey&&e.key.startsWith('Arrow'))return;
 if(e.key==='?'||e.key==='F1'){e.preventDefault();$('shortcut-dialog').showModal();pulseShortcut('#shortcut-help');return;}
 const act={Space:play,ArrowLeft:()=>seek(viewTime-1),ArrowRight:()=>seek(viewTime+1),ArrowUp:()=>navigate(-1),ArrowDown:()=>navigate(1,!e.shiftKey),Digit1:()=>chooseVerdict('correct'),Digit2:()=>chooseVerdict('error'),Digit3:()=>chooseVerdict('uncertain'),KeyF:()=>setAutoFollow(!autoFollow),KeyM:manual,KeyR:replay,KeyA:()=>$('full-scan').click(),Equal:()=>$('zoom-in').click(),NumpadAdd:()=>$('zoom-in').click(),Minus:()=>$('zoom-out').click(),NumpadSubtract:()=>$('zoom-out').click(),Digit0:()=>$('fit').click()}[e.code];
 if(act){e.preventDefault();const selector=e.code==='ArrowDown'?(e.shiftKey?'#next':'#next-pending'):shortcutButtons[e.code];const enabled=selector&&!document.querySelector(selector)?.disabled;act();if(enabled)pulseShortcut(selector);}
});
audio.addEventListener('timeupdate',()=>{if(dragState)return;if(boundedEnd!==null&&audio.currentTime>=boundedEnd){audio.pause();boundedEnd=null;}viewTime=audio.currentTime;followPlayback();requestDraw();try{sessionStorage.setItem(storageKey+'-position',JSON.stringify({position:viewTime,selectedId:selected?.id}));}catch(e){}});
let animationFrame;function animate(){if(!dragState)viewTime=audio.currentTime;followPlayback();draw();if(!audio.paused)animationFrame=requestAnimationFrame(animate);}audio.addEventListener('play',()=>{followPlayback(true);$('play').innerHTML='❚❚ 停止 <kbd>Space</kbd>';cancelAnimationFrame(animationFrame);animationFrame=requestAnimationFrame(animate)});audio.addEventListener('pause',()=>{$('play').innerHTML='▶ 再生 <kbd>Space</kbd>';cancelAnimationFrame(animationFrame);requestDraw()});audio.addEventListener('loadedmetadata',()=>{if(pendingSeek!==null){audio.currentTime=pendingSeek;pendingSeek=null;}requestDraw()});audio.addEventListener('error',()=>{$('notice').textContent='音声ファイルを読み込めません。接続を確認してください。'});window.addEventListener('resize',layoutOverview);window.addEventListener('beforeunload',e=>{if(dirty>persisted){e.preventDefault();e.returnValue=''}});
select(candidates().find(f=>f.id===restored?.selectedId)||candidates()[0]||null,false);if(restored?.position)setTime(restored.position);else if(selected)setTime(findingSpan(selected).start_s-.6);autoFollow=audioTimed;try{const pref=localStorage.getItem(storageKey+'-follow');if(pref!==null)autoFollow=pref==='true'}catch(e){}setAutoFollow(autoFollow,false);saveLabel();layoutOverview();loadMedia();
