import {createClaimService} from './services/index.js';
import {escape,types,statuses,isReady,shell,serviceInfo,guided,guidedChoices,selection,workspace,summary,uploadDialog,analysisResult,docCard} from './components.js';

const params=new URLSearchParams(location.search);
// 顯式設定，API失敗時不會轉成Mock。
const mode=params.get('service')||import.meta.env.VITE_SERVICE_MODE||'mock';
const service=createClaimService({mode});
const state={case:null,claimTypes:[],source:null,health:null,selected:null,directConditions:{},guidedChoice:null,assistantOpen:false,editing:false,route:'triage',busy:false};
const app=document.querySelector('#app');
const home=document.querySelector('#viewTriage');
// 初始服務載入期間不接受輸入，避免初始化完成時覆寫使用者草稿。
home.querySelectorAll('button').forEach(button=>button.disabled=true);
let retryOperation=null,toastTimer=null,currentFile=null,previewUrl=null,activeDoc=null,dialogTrigger=null;
let injectMessageError=params.get('mock_error')==='message';
let pdfPreview=null,pdfPage=1,fileSelectionVersion=0,fileChecking=false;
let directFlowVersion=0,printConditionSnapshot=null;
let guidedFlowVersion=0,guidedChoiceVersion=0,guidedResponsePending=false;
const storageKey=`cardif-active-${mode}-v1`;
const remembered=()=>{try{return sessionStorage.getItem(storageKey)}catch{return null}};
function remember(id){try{id?sessionStorage.setItem(storageKey,id):sessionStorage.removeItem(storageKey)}catch{notify('無法保存瀏覽器進度，重新整理後可能需要重新開始。')}}
function notify(message){const el=document.querySelector('#toast');el.textContent=message;el.classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('visible'),4000)}
function errorMessage(error){return error?.message||'服務暫時無法完成操作，請稍後重試。'}
function showError(error,operation,target='#global-error'){const el=document.querySelector(target);if(!el){notify(errorMessage(error));return}retryOperation=operation;el.innerHTML=`<div class="error-box" role="alert"><span>${escape(errorMessage(error))}</span>${operation?'<button class="btn small" data-action="retry">重試</button>':''}</div>`}
async function action(operation,{busy='正在處理，請稍候…',target='#global-error',progress='#busy-status'}={}){if(state.busy){notify('上一個操作仍在處理，請稍候。');return}state.busy=true;syncGuidedPicker();const err=document.querySelector(target);if(err)err.innerHTML='';const status=document.querySelector(progress);if(status)status.innerHTML=`<div class="busy">${escape(busy)}</div>`;document.querySelectorAll('button[type="submit"]').forEach(b=>b.disabled=true);try{await operation();retryOperation=null}catch(e){showError(e,()=>action(operation,{busy,target,progress}),target)}finally{state.busy=false;const status=document.querySelector(progress);if(status)status.innerHTML='';document.querySelectorAll('button[type="submit"], input[type="file"], #scenario').forEach(b=>b.disabled=false);syncUploadButton();syncGuidedPicker()}}
function clearGuidedChoice(){state.guidedChoice=null;guidedChoiceVersion++;retryOperation=null}
function invalidateGuidedFlow(){guidedFlowVersion++;guidedResponsePending=false;clearGuidedChoice()}
function setCase(c){if(state.case?.id!==c.id)clearGuidedChoice();state.case=c;remember(c.id)}
function beginDirectFlow({claimType=null,conditions={},editing=false}={}){invalidateGuidedFlow();directFlowVersion++;state.selected=claimType;state.directConditions={...conditions};state.editing=editing;retryOperation=null}
function currentGuidedContext(){return guidedResponsePending?null:guidedChoices(state.case,state.claimTypes)}
function currentGuidedChoice(context=currentGuidedContext()){const choice=state.guidedChoice;return context&&choice&&choice.caseId===context.caseId&&choice.responseKey===context.responseKey&&choice.flowVersion===guidedFlowVersion&&context.catalog.some(t=>t.id===choice.type)?choice:null}
function syncGuidedPicker(){const context=currentGuidedContext(),choice=currentGuidedChoice(context),picker=document.querySelector('.guided-type-picker'),button=document.querySelector('[data-action="build-guided-checklist"]');if(picker){picker.hidden=!context;picker.disabled=state.busy||!context;picker.querySelectorAll('input[name="guided-claim-type"]').forEach(input=>{input.checked=input.value===choice?.type;input.disabled=state.busy||!context||!context.catalog.some(t=>t.id===input.value)})}if(button){button.hidden=!context;button.disabled=state.busy||!choice}}
function go(route){if(location.hash===`#${route}`)render(route);else location.hash=route}
function render(route=location.hash.slice(1)||'triage'){
  if(!['triage','assistant','search','workspace','summary'].includes(route))route='triage';
  if(['workspace','summary'].includes(route)&&!state.case?.claim_type_id)route='search';
  state.route=route;home.hidden=route!=='triage';app.hidden=route==='triage';
  document.querySelector('#homeResume').hidden=!state.case?.claim_type_id;
  const homeMode=home.querySelector('.mode-indicator');
  if(homeMode)homeMode.textContent=mode==='mock'?'模擬展示':'展示原型';
  const homeService=home.querySelector('.service-info');
  if(homeService)homeService.outerHTML=serviceInfo(mode,state.health);
  const skipLink=document.querySelector('.skip-link');
  if(skipLink)skipLink.href=route==='triage'?'#home-main-content':'#main-content';
  if(route==='triage'){document.title='理賠申請，需要什麼？｜法國巴黎人壽';window.scrollTo(0,0);return}
  let body='';
  if(route==='assistant')body=guided(state.case?.entry_path==='guided'?state.case:null,mode,{claimTypes:state.claimTypes,selectedType:currentGuidedChoice()?.type,busy:state.busy,pending:guidedResponsePending});
  if(route==='search')body=selection(state.claimTypes,state.selected,state.directConditions,mode);
  if(route==='workspace')body=workspace(state.case,state.assistantOpen,mode);
  if(route==='summary')body=summary(state.case,state.source);
  app.innerHTML=shell(body,{mode,hasCase:!!state.case?.claim_type_id,route,health:state.health});
  syncGuidedPicker();
  document.title=({assistant:'AI 智慧引導',search:'文件快速搜尋',workspace:'文件準備工作區',summary:'送件前準備摘要'})[route]+'｜法國巴黎人壽';
  document.querySelectorAll('.chat-thread').forEach(el=>el.scrollTop=el.scrollHeight);
  document.querySelector('#main-content')?.focus({preventScroll:true});
}
async function ensureGuidedCase(flowVersion){if(flowVersion!==guidedFlowVersion)return null;if(state.case?.entry_path==='guided'&&!state.case.claim_type_id)return state.case;const c=await service.createCase({entry_path:'guided'});if(flowVersion!==guidedFlowVersion)return null;setCase(c);return c}
async function sendGuided(message,flowVersion){try{if(flowVersion!==guidedFlowVersion)return;const c=await ensureGuidedCase(flowVersion);if(!c||flowVersion!==guidedFlowVersion)return;if(injectMessageError&&mode==='mock'){service.simulateFailure();injectMessageError=false}const result=await service.sendMessage(c.id,message);if(flowVersion!==guidedFlowVersion||state.case?.id!==c.id)return;setCase(result.case);clearGuidedChoice();guidedResponsePending=false;render();if(state.route==='assistant')document.querySelector('#guided-input')?.focus()}catch(error){if(flowVersion!==guidedFlowVersion)return;throw error}}
function getDoc(id){return state.case?.documents.find(d=>d.id===id)}
function closeDialog(){const dialog=document.querySelector('dialog');if(!dialog)return;fileSelectionVersion++;fileChecking=false;pdfPreview?.destroy().catch(()=>{});pdfPreview=null;const docId=activeDoc;dialog.close();document.querySelector('#dialog-root').innerHTML='';if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;currentFile=null;activeDoc=null;if(state.route==='workspace')render('workspace');const selector=CSS.escape(docId||'');const trigger=document.querySelector(`[data-action="upload"][data-doc="${selector}"], [data-action="result"][data-doc="${selector}"]`);(trigger||dialogTrigger)?.focus();dialogTrigger=null}
function openDialog(id){const doc=getDoc(id);if(!doc)return;dialogTrigger=document.activeElement;activeDoc=id;currentFile=null;document.querySelector('#dialog-root').innerHTML=uploadDialog(doc,mode);const dialog=document.querySelector('dialog');dialog.addEventListener('cancel',e=>{e.preventDefault();closeDialog()});dialog.showModal();syncUploadButton();dialog.querySelector('.dialog-close').focus()}
function validateFile(file){if(!file)return '請先選擇文件。';if(file.size===0)return '檔案是空白的，請重新選擇。';if(file.size>10*1024*1024)return '檔案不可超過 10 MB，請壓縮後再選擇。';if(!['application/pdf','image/jpeg','image/png'].includes(file.type)||!/^.+\.(pdf|jpe?g|png)$/i.test(file.name))return '格式不支援，請選擇 PDF、JPG、PNG。';return null}
function syncUploadButton(){const button=document.querySelector('form[data-form="analyze"] button[type="submit"]');if(button)button.disabled=state.busy||fileChecking||!currentFile}
async function selectFile(file){if(state.busy){notify('文件正在分析，請完成後再更換檔案。');return}const version=++fileSelectionVersion;const previousResults=document.querySelector('#analysis-results');if(previousResults)previousResults.innerHTML='';pdfPreview?.destroy().catch(()=>{});pdfPreview=null;pdfPage=1;currentFile=null;fileChecking=false;syncUploadButton();const err=validateFile(file);const el=document.querySelector('#upload-error');el.innerHTML=err?`<div class="error-box">${escape(err)}</div>`:'';document.querySelector('#file-info').textContent=file?`${file.name} · ${(file.size/1024).toFixed(1)} KB`:'尚未選擇檔案';if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;if(err)return;
  if(file.type==='application/pdf'){fileChecking=true;syncUploadButton();document.querySelector('#file-info').textContent+=' · 正在檢查PDF頁數…';try{const {inspectPdf}=await import('./pdf-preview.js');const result=await inspectPdf(file);if(version!==fileSelectionVersion){await result.destroy();return}pdfPreview=result;document.querySelector('#file-info').textContent=`${file.name} · ${(file.size/1024).toFixed(1)} KB · ${result.pageCount} 頁`}catch(error){if(version===fileSelectionVersion)showError(error,null,'#upload-error');return}finally{if(version===fileSelectionVersion){fileChecking=false;syncUploadButton()}}}
  if(version===fileSelectionVersion){currentFile=file;previewUrl=URL.createObjectURL(file);syncUploadButton()}
}
function refreshAnalysis(){const doc=getDoc(activeDoc),region=document.querySelector('#analysis-results');if(doc&&region){region.innerHTML=analysisResult(doc,mode,previewUrl,currentFile?.type,{ready:!!pdfPreview,pageNumber:pdfPage,pageCount:pdfPreview?.pageCount});const canvas=document.querySelector('#pdf-canvas');if(canvas&&pdfPreview)pdfPreview.render(canvas,pdfPage).catch(error=>{if(canvas.isConnected&&error?.name!=='RenderingCancelledException')notify('PDF預覽暫時無法繪製，請重新選取文件。')})}}
function downloadSummary(){const c=state.case;const lines=['理賠文件準備摘要（展示原型）',`類型：${types[c.claim_type_id]}`,`日期：${new Date().toLocaleDateString('zh-TW',{timeZone:'Asia/Taipei'})}`,'這是文件準備紀錄，不是理賠核准、送件證明或給付保證。','',...c.documents.map(d=>`${d.title}：${statuses[d.status]}${d.analysis?'；初步檢查 '+d.analysis.analysis_status:''}\n官方依據：${d.official_url}`),'','請依官方程序送件：https://life.cardif.com.tw/zh/a314','請查核個別保單與正式審核；本系統未提交任何理賠。'];const url=URL.createObjectURL(new Blob(['\uFEFF'+lines.join('\n')],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='理賠文件準備摘要.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('準備摘要已下載。')}
document.addEventListener('click',async e=>{
  const skipLink=e.target.closest('.skip-link');
  if(skipLink){e.preventDefault();const main=home.hidden?app.querySelector('#main-content'):home.querySelector('#home-main-content');if(main){main.focus({preventScroll:true});const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;main.scrollIntoView({behavior:reduced?'auto':'smooth',block:'start'})}return}
  const routeBtn=e.target.closest('[data-route]');if(routeBtn){e.preventDefault();if(routeBtn.dataset.route==='search'&&home.contains(routeBtn))beginDirectFlow();go(routeBtn.dataset.route);return}
  const button=e.target.closest('[data-action]');if(!button)return;
  const name=button.dataset.action;
  if(name==='resume'){go(state.case?.claim_type_id?'workspace':'assistant');return}
  if(name==='select-type'){const form=document.querySelector('form[data-form="direct"]');if(form)state.directConditions=Object.fromEntries(new FormData(form));state.selected=button.dataset.type;render('search');return}
  if(name==='build-guided-checklist'){
    if(state.busy){notify('上一個操作仍在處理，請稍候。');return}
    const context=currentGuidedContext(),choice=currentGuidedChoice(context);
    if(!choice){syncGuidedPicker();notify('請先選擇理賠類型。');return}
    const snapshot={caseId:choice.caseId,responseKey:choice.responseKey,type:choice.type,flowVersion:guidedFlowVersion,choiceVersion:guidedChoiceVersion,conditions:{...(context.response.proposed_case_updates?.conditions||{})}};
    const current=()=>{const latest=currentGuidedContext(),selected=currentGuidedChoice(latest);return snapshot.flowVersion===guidedFlowVersion&&snapshot.choiceVersion===guidedChoiceVersion&&latest?.caseId===snapshot.caseId&&latest?.responseKey===snapshot.responseKey&&selected?.type===snapshot.type};
    action(async()=>{if(!current())return;let result;try{result=await service.updateCase(snapshot.caseId,{claim_type_id:snapshot.type,conditions:snapshot.conditions})}catch(error){if(!current())return;throw error}if(!current())return;setCase(result);invalidateGuidedFlow();if(state.route==='assistant')go('workspace');notify('已建立文件準備清單。')},{busy:'正在整理官方文件清單…'});return
  }
  if(name==='prompt'){document.querySelector('#guided-input').value=button.dataset.prompt;document.querySelector('#guided-input').focus();return}
  if(name==='toggle-assistant'){state.assistantOpen=!state.assistantOpen;render('workspace');document.querySelector('[data-action="toggle-assistant"]')?.focus({preventScroll:true});return}
  if(name==='edit-case'){beginDirectFlow({claimType:state.case.claim_type_id,conditions:state.case.conditions,editing:true});go('search');return}
  if(name==='delete-case'){if(!confirm('清除本次測試案件、對話與分析紀錄？請先下載需要保留的準備摘要。'))return;action(async()=>{invalidateGuidedFlow();await service.deleteCase(state.case.id);state.case=null;state.selected=null;state.directConditions={};state.assistantOpen=false;state.editing=false;remember(null);go('triage');notify('已清除本次測試案件。')});return}
  if(name==='upload'||name==='result'){openDialog(button.dataset.doc);return}
  if(name==='close-dialog'){closeDialog();return}
  if(name==='finding'){const target=document.querySelector(`[data-finding-id="${CSS.escape(button.dataset.finding)}"]`);document.querySelectorAll('.finding').forEach(el=>el.classList.remove('selected'));if(target){target.classList.add('selected');const details=target.querySelector('.finding-details');if(details)details.open=true;target.focus({preventScroll:true});const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;target.scrollIntoView({behavior:reduced?'auto':'smooth',block:'nearest'})}return}
  if(name==='confirm-finding'){action(async()=>{const d=getDoc(button.dataset.doc);setCase(await service.updateDocument(state.case.id,d.id,{confirmed_findings:[...new Set([...d.confirmed_findings,button.dataset.finding])]}));refreshAnalysis();notify('已記錄人工確認，仍須對照官方要求。')},{target:'#upload-error',progress:'#upload-progress'});return}
  if(name==='retry'){const op=retryOperation;retryOperation=null;op?.();return}
  if(name==='simulate-error'){service.simulateFailure?.();notify('已設定下一次服務呼叫失敗；可於錯誤提示中重試。');return}
  if(name==='download-summary'){downloadSummary();return}
  if(name==='print-summary'){window.print();return}
});
document.addEventListener('submit',e=>{
  const form=e.target.closest('[data-form]');if(!form)return;e.preventDefault();const data=new FormData(form);
  if(form.dataset.form==='guided'){const message=String(data.get('message')||'').trim();if(message){if(state.busy){notify('上一個操作仍在處理，請稍候。');return}guidedFlowVersion++;clearGuidedChoice();guidedResponsePending=true;syncGuidedPicker();const flowVersion=guidedFlowVersion;action(()=>sendGuided(message,flowVersion),{busy:'正在釐清就醫情況…'})}return}
  if(form.dataset.form==='direct'){
    const conditions=Object.fromEntries(data);const claim_type_id=state.selected;
    const editingCaseId=state.editing?state.case.id:null,flowVersion=directFlowVersion;
    state.directConditions=conditions;
    action(async()=>{let c;try{c=editingCaseId?await service.updateCase(editingCaseId,{claim_type_id,conditions}):await service.createCase({entry_path:'direct',claim_type_id,conditions})}catch(error){if(flowVersion!==directFlowVersion)return;throw error}if(flowVersion!==directFlowVersion)return;setCase(c);state.editing=false;state.selected=null;state.directConditions={};directFlowVersion++;if(state.route==='search')go('workspace');notify('文件清單已建立，請逐項確認。')},{busy:'正在整理官方文件清單…'});return
  }
  if(form.dataset.form==='workspace-chat'){const message=String(data.get('message')||'').trim();if(message)action(async()=>{const result=await service.sendMessage(state.case.id,message);setCase(result.case);render()},{busy:'正在查找可支持的官方資訊…'});return}
  if(form.dataset.form==='analyze'){
    if(fileChecking){notify('正在檢查PDF頁數，請稍候。');return}
    const error=validateFile(currentFile);if(error){showError(new Error(error),null,'#upload-error');return}
    const file=currentFile,id=form.dataset.doc,scenario=String(data.get('scenario')||'missing');
    const caseId=state.case.id;
    action(async()=>{document.querySelectorAll('#document-file,#scenario').forEach(input=>input.disabled=true);const result=await service.analyzeDocument(caseId,id,file,{scenario});if(state.case?.id!==caseId)return;setCase(result);if(activeDoc===id&&document.querySelector('dialog[open]')){refreshAnalysis();document.querySelector('#analysis-results')?.scrollIntoView({behavior:'smooth',block:'start'})}else if(!document.querySelector('dialog[open]'))render();notify(mode==='mock'?'模擬分析已完成，請查看指定情境結果。':'文件初步檢查已完成，請人工覆核。')},{busy:mode==='mock'?'正在執行模擬分析…':'正在擷取文件文字與分析欄位…',target:'#upload-error',progress:'#upload-progress'});return
  }
});
document.addEventListener('change',e=>{
  if(e.target.name==='guided-claim-type'){const context=currentGuidedContext();if(state.busy||!context||!context.catalog.some(t=>t.id===e.target.value)){syncGuidedPicker();return}clearGuidedChoice();state.guidedChoice={caseId:context.caseId,responseKey:context.responseKey,type:e.target.value,flowVersion:guidedFlowVersion};const error=document.querySelector('#global-error');if(error)error.innerHTML='';syncGuidedPicker();return}
  if(e.target.id==='surgery'&&e.target.value==='yes'){const details=document.querySelector('form[data-form="direct"] .advanced-options');if(details)details.open=true;return}
  if(e.target.id==='pdf-page'){pdfPage=Number(e.target.value);refreshAnalysis();return}
  if(e.target.id==='document-file'){selectFile(e.target.files[0]);return}
  if(e.target.matches('[data-status-doc]')&&e.target.value){const id=e.target.dataset.statusDoc,status=e.target.value;action(async()=>{setCase(await service.updateDocument(state.case.id,id,{status}));render('workspace');notify('已更新準備狀態。')});return}
});
document.addEventListener('input',e=>{if(e.target.id==='doc-search'){const q=e.target.value.trim();const next=state.case.documents.find(d=>!isReady(d));const docs=state.case.documents.filter(d=>(d.title+' '+d.description).includes(q));document.querySelector('#document-list').innerHTML=docs.length?docs.map(d=>docCard(d,{isNext:d.id===next?.id})).join(''):'<div class="panel empty">找不到符合的文件，請調整搜尋內容。</div>'}});
document.addEventListener('dragover',e=>{const zone=e.target.closest('#drop-zone');if(zone){e.preventDefault();zone.classList.add('dragover')}});
document.addEventListener('dragleave',e=>e.target.closest('#drop-zone')?.classList.remove('dragover'));
document.addEventListener('drop',e=>{const zone=e.target.closest('#drop-zone');if(zone){e.preventDefault();zone.classList.remove('dragover');const file=e.dataTransfer.files[0];if(file){const dt=new DataTransfer();dt.items.add(file);document.querySelector('#document-file').files=dt.files;selectFile(file)}}});
window.addEventListener('hashchange',()=>{closeDialog();render();window.scrollTo(0,0)});
window.addEventListener('beforeprint',()=>{if(printConditionSnapshot!==null)return;printConditionSnapshot=app.hidden?[]:[...app.querySelectorAll('details.summary-conditions')].map(element=>({element,open:element.open}));for(const item of printConditionSnapshot)if(!item.open)item.element.open=true});
window.addEventListener('afterprint',()=>{if(printConditionSnapshot===null)return;for(const item of printConditionSnapshot)if(item.element.isConnected)item.element.open=item.open;printConditionSnapshot=null});
async function init(){try{state.health=await service.health();state.claimTypes=await service.getClaimTypes();state.source=await service.getSource('cardif-claims');const id=remembered();if(id){try{setCase(await service.getCase(id))}catch(e){if(e.status===404){remember(null);notify('先前測試案件已到期，請重新開始。')}else throw e}}home.querySelectorAll('button').forEach(button=>button.disabled=false);render()}catch(e){home.hidden=true;app.hidden=false;const skipLink=document.querySelector('.skip-link');if(skipLink)skipLink.href='#main-content';app.innerHTML=shell(`<main id="main-content" tabindex="-1" class="page"><div class="page-head"><h1>服務暫時無法使用</h1><p>${escape(errorMessage(e))}</p></div><div class="callout">目前設定為 ${escape(mode.toUpperCase())} 模式。請確認服務啟動後重試。</div><div id="global-error"></div><div class="toolbar"><button class="btn primary" data-action="retry">重試</button><a class="btn" href="https://life.cardif.com.tw/zh/a314" target="_blank" rel="noopener noreferrer">前往官方資訊</a></div></main>`,{mode,hasCase:false,health:state.health});retryOperation=init}}
init();
