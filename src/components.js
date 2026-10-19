export const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const statuses = {not_started:'尚未準備',uploaded:'已上傳／自行備妥',processing:'分析中',precheck_passed:'初步檢查未見指定缺漏',needs_attention:'需要補充或人工確認',not_applicable:'已確認不適用'};
export const requirements = {required:'必備',conditional:'條件式',optional:'選備',unknown:'待確認'};
export const types = {inpatient:'住院醫療',outpatient:'醫療門診',critical_illness:'防癌或重大疾病'};
export const isReady = d => ['uploaded','precheck_passed','not_applicable'].includes(d.status);
export function officialUrl(value){try{const u=new URL(value);return u.protocol==='https:'&&u.hostname==='life.cardif.com.tw'&&!u.username&&!u.password?u.href:null}catch{return null}}
export function sourceLink(source,label){const url=officialUrl(source?.official_url);return url?`<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(label||source.title||'官方來源')} ↗</a>`:'<span class="muted">來源待確認，請查閱官方理賠頁面。</span>'}
export function references(refs=[]){return `<div class="references">${refs.map(s=>typeof s==='object'?sourceLink(s):'').join('')}</div>`}
export function messages(items=[]){return items.map(m=>`<div class="bubble ${m.role==='user'?'user':''}"><div class="speaker">${m.role==='user'?'您':'理賠準備助手'}</div><div>${escape(m.content||m.message||m.text||'')}</div>${m.role!=='user'?references(m.response?.source_references||m.source_references||[]):''}</div>`).join('')}
export function breadcrumbs(route){return `<nav aria-label="準備流程" class="breadcrumbs"><a href="#triage">首頁</a><span aria-hidden="true">›</span><span class="${['assistant','search'].includes(route)?'active':''}">01 確認需求</span><span aria-hidden="true">›</span><span class="${route==='workspace'?'active':''}">02 準備文件</span><span aria-hidden="true">›</span><span class="${route==='summary'?'active':''}">03 送件前摘要</span></nav>`}

export function serviceInfo(mode,health){
  let label='Mock · 對話與 OCR 模擬';
  let description='對話與 OCR 為固定情境模擬，不會呼叫真實 AI 或 OCR。';
  if(mode==='api'){
    if(!health){label='API · 後端服務';description='尚無法確認後端的模型與辨識服務狀態。';}
    else if(health.llm_provider==='grounded_rules'){
      label='API · 官方資料規則引導（非生成式 LLM）';
      description='目前以官方資料檢索與規則整理回答，未啟用生成式 LLM。文件檢查依實際擷取或 OCR 結果處理。';
    }else if(health.llm_configured){
      label='API · 生成式模型已設定';
      description=health.llm_verified?'已完成實際請求驗證，回答仍須依官方來源與保單確認。':'尚未完成實際請求驗證；設定存在不代表模型服務已驗證。';
    }else{
      label='API · 對話服務尚未設定';
      description='尚未完成對話模型設定與驗證。服務失敗不會自動切換至規則引導或模擬服務。';
    }
  }
  return `<details class="service-info"><summary>服務說明</summary><div class="service-popover"><p class="mode-label">${escape(label)}</p><p>${escape(description)}</p><p>本系統協助準備文件，不判定理賠資格、不保證給付，也不代送申請。請依官方規範、保單條款與正式審核確認。</p><p>請勿輸入真實身分或醫療資訊。可於工作區清除準備紀錄；原始文件不會保存，重新開啟須重選。</p>${debugTools(mode)}</div></details>`;
}
export function shell(body,{mode,hasCase,route,health}){
  return `<div class="app-shell"><header class="app-header"><button data-route="triage" class="brand-button" aria-label="返回首頁"><img src="/assets/brand.png" alt="BNP PARIBAS CARDIF 法國巴黎人壽"></button><nav class="header-nav" aria-label="主要導覽"><span class="mode-indicator">${mode==='mock'?'模擬展示':'展示原型'}</span><a href="https://life.cardif.com.tw/zh/a314" target="_blank" rel="noopener noreferrer" class="small">官方理賠資訊 ↗</a>${hasCase&&route!=='workspace'?'<button class="text-link" data-action="resume">繼續準備</button>':''}<button class="text-link" data-route="triage">返回首頁</button></nav></header>${body}<footer class="app-footer"><p>展示原型 · 請使用虛構資料。初步檢查不代表正式審核或理賠核准。</p>${serviceInfo(mode,health)}</footer></div>`;
}
export function errorRegion(){return '<div id="global-error" aria-live="assertive"></div><div id="busy-status" role="status" aria-live="polite"></div>'}
export function debugTools(mode){return mode==='mock'?'<details class="debug-tools"><summary>展示測試工具</summary><button class="btn small" data-action="simulate-error">模擬下次服務錯誤</button><p>只影響下一次服務呼叫，可於錯誤提示中重試。</p></details>':''}

export function guided(c,mode){
  const last=[...(c?.messages||[])].reverse().find(m=>m.role!=='user');
  const suggestions=last?.response?.suggested_claim_types||last?.suggested_claim_types||[];
  return `<main id="main-content" tabindex="-1" class="page">${breadcrumbs('assistant')}<div class="page-head"><h1>讓我們協助您的理賠流程</h1><p>描述就醫情況，從需要的文件開始。</p></div><div class="guided-layout guided-focus"><section class="panel conversation-panel"><div class="chat-thread" id="guided-thread" role="log" aria-label="引導對話">${c?.messages?.length?messages(c.messages):'<div class="empty"><h2>先從您的情況開始</h2><p>例如：車禍後住院三天，沒有手術。</p></div>'}</div>${suggestions.length?`<div class="suggested-types spaced"><strong>可能相關的類型，請您確認</strong><div class="prompt-chips">${suggestions.map(s=>{const id=typeof s==='string'?s:s.id||s.claim_type_id;return `<button class="btn${suggestions.length===1?' primary':''}" data-action="confirm-suggestion" data-type="${escape(id)}">確認並建立清單${suggestions.length>1?'：'+escape(types[id]||id):''}</button>`}).join('')}</div></div>`:''}${errorRegion()}<form class="chat-form" data-form="guided"><label for="guided-input">描述就醫情況</label><div class="input-bar"><input id="guided-input" name="message" maxlength="2000" required placeholder="例如：車禍後住院三天，沒有手術" autocomplete="off"><button class="btn${suggestions.length?'':' primary'}" type="submit" aria-label="送出描述">送出描述 ↑</button></div></form><div class="prompt-chips"><button data-action="prompt" data-prompt="我因車禍住院三天，沒有接受手術">意外事故住院</button><button data-action="prompt" data-prompt="我只有門診治療，沒有住院">只有門診治療</button><button data-action="prompt" data-prompt="可能是重大疾病，但我還不確定">保單條款不確定</button></div><p class="section-note">請勿提供姓名、身分證字號或病歷。</p><a class="small" href="#search">已知道類型？直接選擇 →</a></section></div></main>`;
}

export function selection(claimTypes,selected,conditions={},mode){
  const advancedOpen=selected==='critical_illness'||conditions.surgery==='yes';
  return `<main id="main-content" tabindex="-1" class="page">${breadcrumbs('search')}<div class="page-head"><h1>快速查找理賠所需文件</h1><p>選擇理賠類型。</p></div><div class="choice-grid">${claimTypes.map((t,i)=>`<button aria-label="${escape(t.title||t.label)}" class="choice ${selected===t.id?'selected':''}" aria-pressed="${selected===t.id}" data-action="select-type" data-type="${escape(t.id)}"><div class="icon" aria-hidden="true">${['▤','＋','♡'][i]||'▤'}</div><h2>${escape(t.title||t.label)}</h2></button>`).join('')}</div>${selected?`<section class="panel selection-panel spaced"><h2>${escape(types[selected])} · 確認準備條件</h2><p class="section-note">不知道的項目可保留「尚不確定」。</p><form data-form="direct"><div class="form-grid">${selectField('cause','事故原因',[['unknown','尚不確定'],['accident','意外事故'],['illness','疾病']],conditions.cause)}${selectField('surgery','是否接受手術',[['unknown','尚不確定'],['yes','有接受手術'],['no','沒有接受手術']],conditions.surgery)}${selectField('receipt_type','收據用途',[['unknown','尚不確定'],['actual','實支實付／費用理賠'],['daily','日額型，仍需查核保單']],conditions.receipt_type)}</div><details class="advanced-options"${advancedOpen?' open':''}><summary>更多準備條件</summary><div class="form-grid">${selectField('payment_method','預計給付方式',[['unknown','尚不確定'],['remittance','匯款'],['other','其他方式，需洽官方']],conditions.payment_method)}${selectField('first_claim','是否首次申請癌症／重大疾病',[['unknown','尚不確定'],['yes','首次申請'],['no','不是首次申請']],conditions.first_claim)}${selectField('diagnosis_has_surgery_details','診斷書是否載明手術部位及方式',[['unknown','尚不確定'],['yes','已記載'],['no','未記載']],conditions.diagnosis_has_surgery_details)}</div></details>${errorRegion()}<div class="form-actions"><button type="submit" aria-label="建立文件清單" class="btn primary">建立文件清單 →</button></div></form></section>`:''}</main>`;
}
function selectField(id,title,opts,value){return `<div><label for="${id}">${title}</label><select name="${id}" id="${id}">${opts.map(([v,l])=>`<option value="${v}" ${String(value||'unknown')===v?'selected':''}>${l}</option>`).join('')}</select></div>`}

export function docCard(d,{isNext=false}={}){
  const refs=d.source_references||[];
  const explanation=d.requirement_explanation||(typeof d.condition==='string'?d.condition:'請依官方說明與保單條款確認適用條件。');
  return `<article class="doc-card${isNext?' next-document':''}" data-document-id="${escape(d.id)}"><div class="doc-head"><div class="doc-title"><span class="doc-icon" aria-hidden="true">▤</span><h2>${escape(d.title)}</h2></div><span class="badge ${d.requirement_type==='unknown'?'warning':d.requirement_type==='required'?'':'neutral'}">${escape(requirements[d.requirement_type]||'待確認')}</span></div><div class="row">${d.applicability===null?'<span class="badge warning">適用條件待確認</span>':''}<span class="badge ${d.status==='needs_attention'?'warning':'neutral'}">${escape(statuses[d.status]||d.status)}</span></div><div class="doc-actions"><button class="btn${isNext?' primary':''} small" data-action="${d.analysis?'result':'upload'}" data-doc="${escape(d.id)}">${d.analysis?'查看檢查結果':'上傳與檢查'}</button>${d.download_url?`<span class="small">${sourceLink({official_url:d.download_url},'官方空白表單')}</span>`:''}</div><details class="document-details"><summary>文件說明與官方來源</summary><p>${escape(d.description)}</p><p>${escape(explanation)}</p>${d.file?`<p class="small">本次文件：${escape(d.file.name||d.file.filename)}${!d.analysis?' · 尚未分析':''}</p>`:''}<div class="source-list">${sourceLink({official_url:d.official_url},'官方應備文件依據')}${d.download_url?sourceLink({official_url:d.download_url},'開啟官方空白表單'):''}${d.example_url?sourceLink({official_url:d.example_url},'官方填寫範例'):''}${refs.map(s=>sourceLink(s)).join('')}</div><p class="small">${d.download_url?'表單由官方網站提供。':'請向原出具單位取得文件。'}來源查核：2026-10-17；版本依官方檔案標示。</p><label for="status-${escape(d.id)}">${escape(d.title)}準備狀態</label><select class="doc-status" id="status-${escape(d.id)}" data-status-doc="${escape(d.id)}"><option value="" selected>更新準備狀態…</option><option value="not_started">尚未準備</option><option value="uploaded">我已自行備妥，尚未檢查</option>${d.requirement_type!=='required'?'<option value="not_applicable">我已確認此條件不適用</option>':''}</select></details></article>`;
}

export function workspace(c,assistantOpen,mode,search=''){
  const docs=c.documents||[];
  const done=docs.filter(isReady).length;
  const next=docs.find(d=>!isReady(d));
  const list=docs.filter(d=>(d.title+' '+d.description).includes(search));
  const pending=docs.some(d=>d.applicability===null||d.requirement_type==='unknown'||d.review_required);
  return `<div class="workspace ${assistantOpen?'':'no-assistant'}"><aside class="case-nav"><h2>${escape(types[c.claim_type_id])}</h2><div class="row between small"><strong>文件準備進度</strong><span>${done} / ${docs.length}</span></div><div class="progress-track" role="progressbar" aria-label="文件準備進度" aria-valuemin="0" aria-valuemax="${docs.length||1}" aria-valuenow="${done}"><span style="width:${docs.length?done/docs.length*100:0}%"></span></div><p class="section-note">含自行備妥與不適用項目。</p><div class="case-actions"><button class="btn${next?'':' primary'}" data-route="summary" aria-label="查看準備摘要">查看準備摘要 →</button></div><details class="case-options"><summary>案件條件與管理</summary><div class="case-meta"><span>事故原因：${{accident:'意外',illness:'疾病'}[c.conditions?.cause]||'待確認'}</span><span>手術情況：${{yes:'有',no:'無'}[c.conditions?.surgery]||'待確認'}</span></div><div class="case-actions"><button class="btn" data-action="edit-case">修改案件條件</button><button class="btn danger" data-action="delete-case">清除測試案件</button></div></details></aside><main id="main-content" tabindex="-1" class="workspace-main">${breadcrumbs('workspace')}<div class="workspace-head spaced"><h1>文件準備工作區</h1><button class="btn small" data-action="toggle-assistant" aria-expanded="${!!assistantOpen}" aria-controls="workspace-assistant">${assistantOpen?'隱藏助手':'開啟助手'}</button></div>${pending?'<p class="section-note">「待確認」不代表免附，請查核保單或向官方確認。</p>':''}${errorRegion()}<label class="sr-only" for="doc-search">搜尋清單文件</label><input id="doc-search" type="search" placeholder="搜尋文件，例如：申請書、診斷" value="${escape(search)}"><div id="document-list" class="doc-list spaced">${list.length?list.map(d=>docCard(d,{isNext:d.id===next?.id})).join(''):'<div class="panel empty">找不到符合的文件，請調整搜尋內容。</div>'}</div></main><aside id="workspace-assistant" class="assistant-panel" aria-label="理賠準備助手"${assistantOpen?'':' hidden'}>${assistantOpen?`<h2>理賠準備助手</h2><p class="section-note">${mode==='mock'?'模擬對話 · ':''}詢問文件用途或準備問題。</p><div class="chat-thread" role="log" aria-label="工作區對話">${c.messages?.length?messages(c.messages):'<div class="bubble">想先了解哪一項文件？</div>'}</div><form data-form="workspace-chat"><label for="workspace-message">詢問文件準備問題</label><textarea id="workspace-message" name="message" maxlength="2000" placeholder="例如：保險金申請書要注意什麼？" required></textarea><button type="submit" class="btn primary">送出問題</button></form>`:''}</aside></div>`;
}

export function summary(c,source){
  const docs=c.documents||[];
  const ready=docs.filter(isReady).length;
  const attention=docs.filter(d=>d.status==='needs_attention').length;
  return `<main id="main-content" tabindex="-1" class="page">${breadcrumbs('summary')}<div class="page-head"><h1>送件前準備摘要</h1><p>${escape(types[c.claim_type_id])}</p></div><div class="callout warning">這份摘要是準備紀錄，不是理賠核准或送件證明。本系統沒有向保險公司提交任何申請。</div><div class="summary-stats"><div class="stat"><strong>${ready}</strong><span>已備妥／已確認不適用</span></div><div class="stat"><strong>${docs.length-ready}</strong><span>尚待處理的文件</span></div><div class="stat"><strong>${attention}</strong><span>需要補充或人工確認</span></div></div><section class="panel"><h2>文件準備紀錄</h2><table class="summary-table spaced"><thead><tr><th scope="col">文件</th><th scope="col">需求</th><th scope="col">目前狀態與初步檢查</th></tr></thead><tbody>${docs.map(d=>`<tr><td>${escape(d.title)}<div class="small">${sourceLink({official_url:d.official_url},'官方依據')}</div></td><td>${escape(requirements[d.requirement_type])}</td><td>${escape(statuses[d.status])}${d.analysis?`<div class="small muted">${d.analysis.analysis_status==='uncertain'?'辨識不確定 · ':''}${(d.analysis.findings||[]).length} 項提醒，仍需人工覆核</div>`:''}</td></tr>`).join('')}</tbody></table><details class="advanced-options summary-conditions"><summary>仍需確認的條件</summary><p class="section-note">${Object.entries(c.conditions||{}).some(([,v])=>v==='unknown'||v===null)?'部分條件尚不明確，請修改條件或向官方洽詢。':'已記錄目前條件，仍請查核個別保單與官方通知。'}</p>${docs.filter(d=>d.requirement_type==='unknown'||d.review_required).map(d=>`<p class="small muted">${escape(d.title)}：${escape(d.requirement_explanation||'請向官方確認是否適用。')}</p>`).join('')}</details></section><section class="panel spaced"><h2>下一步：依官方方式送件</h2><p class="section-note">補齊待處理項目後，請依官方程序辦理。</p>${submissionText(source)}<div class="source-list">${sourceLink(source,'前往官方理賠程序與送件資訊')}</div></section>${errorRegion()}<div class="toolbar"><button class="btn primary" data-action="download-summary">下載摘要</button><button class="btn" data-action="print-summary">列印摘要</button><button class="btn" data-route="workspace">返回工作區</button></div><p class="section-note">下載檔案包含本次準備紀錄，請妥善保管。</p></main>`;
}
function submissionText(s){
  const v=s?.submission;if(!v)return '';
  if(typeof v==='string')return `<div class="callout">${escape(v)}</div>`;
  return `<div class="submission-info">${v.postal?`<h3>郵寄紙本文件</h3><p>${escape(v.postal.address)}<br>${escape(v.postal.recipient)}</p><p class="small">${(v.postal.steps||[]).map(escape).join(' → ')}</p>`:''}${v.support?`<p>官方服務專線：${escape(v.support.phone)} · ${escape(v.support.hours)}</p>`:''}<p class="section-note">送件前請再次核對官方最新資訊。</p></div>`;
}

export function uploadDialog(d,mode){
  return `<dialog aria-labelledby="upload-title"><header class="dialog-header"><div><h2 id="upload-title">文件初步檢查</h2><p class="small muted">${escape(d.title)}</p></div><button class="dialog-close" data-action="close-dialog" aria-label="關閉文件檢查">×</button></header><div class="dialog-body"><span class="mode-indicator">${mode==='mock'?'Mock · 模擬分析，結果不是實際辨識':'API · 實際文件檢查'}</span><p class="section-note upload-note">PDF、JPG、PNG · 單檔 10 MB 以內 · PDF 最多 10 頁</p><p class="section-note">請只上傳虛構文件。簽名須人工確認，初步檢查不代表正式審核。</p><form data-form="analyze" data-doc="${escape(d.id)}"><label class="upload-drop" id="drop-zone" for="document-file">選擇文件<span class="small muted">或拖放至此處</span><input id="document-file" name="file" type="file" aria-label="選擇文件" accept="application/pdf,image/jpeg,image/png" required></label>${mode==='mock'?'<label for="scenario">模擬分析情境</label><select id="scenario" name="scenario"><option value="missing">疑似欄位缺漏</option><option value="complete">未發現指定缺漏</option><option value="blurred">影像模糊，需人工確認</option></select>':''}<div id="upload-error" role="alert"></div><div id="upload-progress" role="status" aria-live="polite"></div><div class="row spaced"><button type="submit" class="btn primary">開始分析</button><span class="small muted" id="file-info">尚未選擇檔案</span></div></form><div id="analysis-results">${d.analysis?analysisResult(d,mode):''}</div></div></dialog>`;
}

export function analysisResult(d,mode,previewUrl,fileType,pdf={}){
  const a=d.analysis;if(!a)return '';
  const quality=a.provider==='quality_precheck';
  const fs=a.findings||[];
  const qualityHints=quality||fs.some(f=>f.field==='image_quality');
  const uncertain=qualityHints||a.analysis_status==='uncertain';
  const boxes=a.bounding_boxes||[];
  const provider=mode==='mock'?'Mock · 模擬OCR':quality?'Real · 文件清晰度預檢（未執行OCR）':a.provider==='pdf_text'?'Real OCR · PDF文字擷取':a.provider==='rapidocr'?'Real OCR · 圖片辨識':'Real OCR · 實際文件分析';
  const notice=mode==='mock'?'以下是固定展示情境的模擬結果，未辨識這份檔案。':quality?'文件清晰度不足，未執行文字辨識；請改傳清晰文件並人工確認。':qualityHints?'部分內容未可靠辨識，需要人工確認，請逐頁核對。':uncertain?'辨識結果不確定，需要人工確認。':'依實際文件擷取結果整理，仍須人工覆核。';
  const findings=fs.map((f,i)=>{
    const id=f.id||f.finding_id||String(i);
    const confirmed=(d.confirmed_findings||[]).includes(id);
    return `<section class="finding ${confirmed?'confirmed':''}" data-finding-id="${escape(id)}" tabindex="-1"><h3>${escape(f.field_name||f.field||f.title||'人工確認項目')}</h3><p>${escape(f.message||f.description||f.issue||'請人工確認文件內容。')}</p>${f.page_number?`<p class="small muted">第 ${escape(f.page_number)} 頁</p>`:''}<details class="finding-details"><summary>檢查方式與官方依據</summary><p>${escape(f.suggestion||'請對照原始文件與官方表單檢查，不確定時洽官方。')}</p><p class="small muted">此為初步提示，可能有辨識誤差。</p>${sourceLink({official_url:f.official_url||d.official_url},mode==='api'&&f.field==='image_quality'?'官方表單參考':'官方依據')}</details><button class="btn small" data-action="confirm-finding" data-doc="${escape(d.id)}" data-finding="${escape(id)}" ${confirmed?'disabled':''}>${confirmed?'已人工確認':'我已人工確認'}</button></section>`;
  }).join('');
  return `<div class="divider"></div><div class="row between"><h2>分析結果</h2><span class="mode-indicator">${mode==='mock'?'Mock · 模擬OCR':quality?'文件清晰度預檢（未執行OCR）':'實際文件檢查'}</span></div><p class="section-note">${notice}</p><details class="analysis-meta"><summary>辨識資訊</summary><p>${escape(provider)}</p><p class="small">${quality?'未執行文字辨識，無文字信心可供參考。':`${mode==='mock'?'模擬情境信心':'初步檢查參考信心'}：${Math.round((a.confidence||0)*100)}%。僅供準備參考，不代表整份文件準確度。`}</p></details><div class="analysis-layout"><div><h3>文件預覽</h3>${previewMarkup(d,mode,previewUrl,fileType,pdf,fs,boxes)}<p class="section-note">${mode==='mock'?'框線為模擬位置示意，並非此檔案的辨識位置。':qualityHints?'清晰度標記為人工提示區域，請對照原始文件。':'框線依辨識位置提供，仍請人工核對。'}</p></div><div><h3>初步檢查發現</h3><div class="spaced">${findings||(quality?'<div class="callout warning">文件清晰度不足，請改傳清晰文件並人工確認。</div>':uncertain?'<div class="callout warning">需要人工確認，尚無足夠內容判斷指定缺漏。</div>':'<div class="callout">初步檢查未發現指定缺漏，仍須核對完整內容與官方文件。</div>')}${a.extracted_fields?.length?`<details class="advanced-options small"><summary>已辨識的指定欄位（仍需核對）</summary>${a.extracted_fields.map(f=>`<p>${escape(f.field_name||f.field)}：${escape(f.value??'無法可靠辨識')}</p>`).join('')}</details>`:''}<p class="section-note">人工確認只記錄已檢視，不會更改辨識結果或代表理賠核准。</p></div></div></div>`;
}

function previewMarkup(d,mode,url,type,pdf,findings,boxes){
  const pageNumber=pdf.pageNumber||1;
  const markers=(type!=='application/pdf'||pdf.ready||mode==='mock')?boxes.filter(b=>(b.page_number||1)===pageNumber).map(b=>{
    const i=boxes.indexOf(b),box=b.box||b.bounding_box||b;
    const x=box.x??box[0]??.1,y=box.y??box[1]??.2,w=box.width??box[2]??.6,h=box.height??box[3]??.08;
    return `<button class="marker" data-action="finding" data-finding="${escape(b.finding_id||findings[i]?.id||i)}" style="left:${Math.max(0,Math.min(1,x))*100}%;top:${Math.max(0,Math.min(1,y))*100}%;width:${Math.max(0,Math.min(1,w))*100}%;height:${Math.max(0,Math.min(1,h))*100}%" aria-label="查看欄位提醒 ${i+1}">${i+1}</button>`;
  }).join(''):'';
  let content='';
  if(pdf.ready){content=`<label for="pdf-page">預覽頁碼</label><select id="pdf-page" aria-label="預覽頁碼">${Array.from({length:pdf.pageCount},(_,i)=>`<option value="${i+1}" ${i+1===pageNumber?'selected':''}>第 ${i+1} / ${pdf.pageCount} 頁</option>`).join('')}</select><div class="pdf-page-frame spaced"><canvas id="pdf-canvas" role="img" aria-label="本次上傳PDF第${pageNumber}頁預覽"></canvas>${markers}</div>`}
  else if(url&&type!=='application/pdf'){content=`<div class="pdf-page-frame"><img src="${escape(url)}" alt="本次上傳文件預覽">${markers}</div>`}
  else{content=`<div class="pdf-page-frame"><div class="mock-page"><strong>${mode==='mock'?'展示位置示意':'本次預覽尚未載入'}</strong><p>原始文件不會保存，關閉或重新整理後請重新選取。</p><div class="mock-line">文件名稱：${escape(d.title)}</div><div class="mock-line">日期：＿＿＿＿＿＿</div><div class="mock-line">簽名：＿＿＿＿＿＿</div></div>${markers}</div>`}
  return `<div class="preview-wrap spaced">${content}</div>`;
}
