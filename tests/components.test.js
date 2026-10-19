import test from 'node:test';
import assert from 'node:assert/strict';
import {officialUrl,sourceLink,summary,isReady,docCard,analysisResult,shell,selection,workspace,guided,messages} from '../src/components.js';

test('official links reject credentials, script URLs, lookalike hosts and non-HTTPS',()=>{
  for(const url of ['javascript:alert(1)','http://life.cardif.com.tw/zh/a314','https://life.cardif.com.tw.evil.test/','https://user@life.cardif.com.tw/'])assert.equal(officialUrl(url),null);
  assert.equal(officialUrl('https://life.cardif.com.tw/zh/a314'),'https://life.cardif.com.tw/zh/a314');
  assert.ok(!sourceLink({official_url:'javascript:alert(1)'}).includes('href='));
});
test('summary shows only official source supplied postal and support guidance',()=>{
  const html=summary({claim_type_id:'inpatient',documents:[],conditions:{}},{official_url:'https://life.cardif.com.tw/zh/a314',submission:{postal:{address:'合成查核地址',recipient:'官方理賠部',steps:['確認投保險種','備齊文件']},support:{phone:'0800-DEMO',hours:'展示時段'}}});
  for(const text of ['合成查核地址','官方理賠部','0800-DEMO','展示時段'])assert.ok(html.includes(text),`${text} should be visible`);
});
test('unknown conditional documents prominently ask for applicability confirmation',()=>{
  const html=docCard({id:'test',title:'合成文件',description:'測試',requirement_type:'conditional',applicability:null,review_required:true,status:'not_started',source_references:[]});
  assert.ok(html.includes('適用條件待確認'));
});
test('a document with attention findings cannot count as ready',()=>{
  assert.equal(isReady({status:'needs_attention'}),false);
  assert.equal(isReady({status:'precheck_passed'}),true);
});

test('quality precheck explains that unreadable input has not undergone OCR',()=>{
  const html=analysisResult({id:'application',confirmed_findings:[],official_url:'https://life.cardif.com.tw/zh/a314',analysis:{provider:'quality_precheck',confidence:0,findings:[],bounding_boxes:[],extracted_fields:[]}},'api');
  assert.ok(html.includes('文件清晰度預檢（未執行OCR）'));
  assert.ok(html.includes('請改傳清晰文件並人工確認'));
  assert.ok(!html.includes('Real OCR'));
  assert.ok(!html.includes('框線依辨識位置'));
  assert.ok(!html.includes('初步檢查未發現指定缺漏'));
});

test('mixed PDF quality hints remain manual references beside actual text extraction',()=>{
  const html=analysisResult({id:'application',confirmed_findings:[],official_url:'https://life.cardif.com.tw/zh/a314',analysis:{provider:'pdf_text',confidence:.99,findings:[{id:'quality-page2',field:'image_quality',field_name:'文件清晰度',page_number:2,message:'第2頁清晰度不足，未辨識。'}],bounding_boxes:[],extracted_fields:[]}},'api');
  assert.ok(html.includes('Real OCR · PDF文字擷取'));
  assert.ok(html.includes('官方表單參考'));
  assert.ok(html.includes('部分內容未可靠辨識'));
  assert.ok(html.includes('初步檢查參考信心'));
  assert.ok(!html.includes('框線依辨識位置'));
});

const sampleDocument=(id,extra={})=>({id,title:`合成文件 ${id}`,description:'文件用途說明',requirement_type:'required',status:'not_started',official_url:'https://life.cardif.com.tw/zh/a314',confirmed_findings:[],...extra});
const sampleCase=(documents=[])=>({id:'sample-case',claim_type_id:'inpatient',conditions:{},documents,messages:[]});
const claimTypes=[{id:'inpatient',title:'住院醫療'},{id:'outpatient',title:'醫療門診'},{id:'critical_illness',title:'防癌或重大疾病'}];

test('service disclosure keeps the visible mode short without treating configuration as verification',()=>{
  const mock=shell('<main>內容</main>',{mode:'mock'});
  assert.match(mock,/<span class="mode-indicator">模擬展示<\/span>/);
  assert.match(mock,/<details class="service-info">[\s\S]*Mock[\s\S]*data-action="simulate-error"[\s\S]*<\/details>/);
  const rules=shell('<main>內容</main>',{mode:'api',health:{llm_provider:'grounded_rules',llm_configured:false,llm_verified:false}});
  assert.match(rules,/<span class="mode-indicator">展示原型<\/span>/);
  assert.ok(rules.includes('非生成式 LLM'));
  assert.ok(!rules.includes('data-action="simulate-error"'));
  const configured=shell('',{mode:'api',health:{llm_configured:true,llm_verified:false}});
  assert.ok(configured.includes('尚未完成實際請求驗證'));
  assert.ok(!configured.includes('已完成實際請求驗證'));
  const unavailable=shell('',{mode:'api',health:{llm_provider:'unconfigured_llm',llm_configured:false,llm_verified:false}});
  assert.ok(unavailable.includes('對話服務尚未設定'));
  assert.ok(!unavailable.includes('目前以官方資料檢索與規則整理回答'));
  const inWorkspace=shell('',{mode:'api',hasCase:true,route:'workspace'});
  assert.ok(!inWorkspace.includes('data-action="resume"'));
});

test('claim selection asks for a type before showing conditions and groups optional detail without dropping fields',()=>{
  const first=selection(claimTypes,null,{},'mock');
  assert.ok(!first.includes('data-form="direct"'));
  assert.equal((first.match(/data-action="select-type"/g)||[]).length,3);
  const selected=selection(claimTypes,'inpatient',{cause:'accident',payment_method:'remittance'},'mock');
  const advanced=selected.match(/<details class="advanced-options"[^>]*>([\s\S]*?)<\/details>/)?.[1];
  assert.ok(advanced,'extra conditions remain accessible in a disclosure');
  for(const field of ['payment_method','first_claim','diagnosis_has_surgery_details'])assert.ok(advanced.includes(`name="${field}"`));
  for(const field of ['cause','surgery','receipt_type'])assert.ok(selected.indexOf(`name="${field}"`)<selected.indexOf('<details class="advanced-options"'));
  assert.match(selected,/<option value="remittance" selected>/);
  assert.equal((selected.match(/<option value="unknown"/g)||[]).length,6);
});

test('claim-specific extra conditions are revealed when relevant',()=>{
  assert.match(selection(claimTypes,'critical_illness',{},'api'),/<details class="advanced-options" open>/);
  assert.match(selection(claimTypes,'inpatient',{surgery:'yes'},'api'),/<details class="advanced-options" open>/);
  assert.match(selection(claimTypes,'inpatient',{},'api'),/<details class="advanced-options">/);
});

test('the next unfinished document owns the workspace primary action and summary takes over only after preparation',()=>{
  const c=sampleCase([sampleDocument('ready',{status:'uploaded'}),sampleDocument('next'),sampleDocument('later')]);
  const html=workspace(c,false,'api');
  assert.equal((html.match(/class="btn primary(?: small)?"/g)||[]).length,1);
  assert.match(html,/<article class="doc-card next-document" data-document-id="next">[\s\S]*?class="btn primary small" data-action="upload" data-doc="next"/);
  assert.ok(!html.includes('data-form="workspace-chat"'));
  assert.match(html,/data-action="toggle-assistant"[^>]*aria-expanded="false"[^>]*aria-controls="workspace-assistant"/);
  const open=workspace(c,true,'api');
  assert.match(open,/id="workspace-assistant"/);
  assert.match(open,/data-action="toggle-assistant"[^>]*aria-expanded="true"/);
  const ready=workspace(sampleCase([sampleDocument('ready',{status:'uploaded'})]),false,'api');
  assert.match(ready,/class="btn primary" data-route="summary"/);
});

test('document secondary details preserve applicability and safe status choices with a single document action',()=>{
  const required=docCard(sampleDocument('required',{applicability:null}),{isNext:true});
  assert.ok(required.includes('適用條件待確認'));
  assert.ok(!required.includes('value="not_applicable"'));
  assert.match(required,/<details class="document-details">[\s\S]*data-status-doc="required"[\s\S]*<\/details>/);
  const analyzed=docCard(sampleDocument('analyzed',{analysis:{findings:[]}}));
  assert.equal((analyzed.match(/data-action="(?:upload|result)"/g)||[]).length,1);
  assert.ok(analyzed.includes('data-action="result"'));
  const conditional=docCard(sampleDocument('conditional',{requirement_type:'conditional'}));
  assert.ok(conditional.includes('value="not_applicable"'));
  const downloadable=docCard(sampleDocument('download',{description:'完整用途放在詳情',download_url:'https://life.cardif.com.tw/official.pdf'}));
  const actions=downloadable.match(/<div class="doc-actions">([\s\S]*?)<\/div>/)?.[1];
  assert.ok(actions.includes('官方空白表單'));
  assert.ok(actions.includes('https://life.cardif.com.tw/official.pdf'));
  assert.ok(downloadable.indexOf('完整用途放在詳情')>downloadable.indexOf('<details class="document-details">'));
  const unsafe=docCard(sampleDocument('unsafe',{download_url:'https://evil.test/form.pdf'}));
  assert.ok(!unsafe.includes('href="https://evil.test/'));
});

test('all preparation statuses expose one honest document action without changing readiness',()=>{
  for(const [status,hasAnalysis] of [['not_started',false],['uploaded',false],['processing',false],['precheck_passed',true],['needs_attention',true],['not_applicable',false]]){
    const d=sampleDocument(status,{status,analysis:hasAnalysis?{findings:[]}:null});
    const ready=isReady(d);
    const html=docCard(d,{isNext:!ready});
    assert.equal((html.match(/data-action="(?:upload|result)"/g)||[]).length,1,`${status} has one document action`);
    assert.ok(html.includes(`data-action="${hasAnalysis?'result':'upload'}"`),`${status} opens the available view`);
    assert.equal(html.includes('class="btn primary small"'),!ready,`${status} keeps the next action prominent`);
    assert.equal(isReady(d),ready,'rendering does not change case readiness');
  }
});

test('uncertain real extraction never presents an all-clear and keeps findings accessible',()=>{
  const html=analysisResult(sampleDocument('uncertain',{analysis:{provider:'pdf_text',analysis_status:'uncertain',confidence:.49,findings:[],bounding_boxes:[],extracted_fields:[]}}),'api');
  assert.ok(html.includes('需要人工確認'));
  assert.ok(!html.includes('初步檢查未發現指定缺漏'));
  const finding=analysisResult(sampleDocument('finding',{analysis:{provider:'rapidocr',analysis_status:'needs_attention',confidence:.8,findings:[{id:'signature',field_name:'簽名',message:'簽名需人工確認',suggestion:'請對照原始文件。'}],bounding_boxes:[],extracted_fields:[]}}),'api');
  assert.match(finding,/<details class="finding-details">/);
  assert.ok(finding.includes('簽名需人工確認'));
  assert.ok(finding.includes('data-action="confirm-finding"'));
});

test('compact renderers continue escaping untrusted document and conversation content',()=>{
  const payload='<img src=x onerror=alert(1)>';
  const doc=docCard(sampleDocument('safe',{title:payload,description:payload}));
  const chat=messages([{role:'assistant',content:payload}]);
  const guidance=guided({messages:[{role:'assistant',content:payload,response:{suggested_claim_types:[]}}]},'mock');
  for(const html of [doc,chat,guidance]){assert.ok(!html.includes(payload));assert.ok(html.includes('&lt;img'));}
  assert.ok(!guidance.includes('data-action="confirm-suggestion"'));
});


test('a confirmed direction makes building the checklist the guided primary action',()=>{
  const first=guided(null,'mock');
  assert.match(first,/<button class="btn primary" type="submit" aria-label="送出描述">/);
  const suggested=guided({messages:[{role:'assistant',content:'請確認準備方向',response:{suggested_claim_types:['inpatient']}}]},'mock');
  assert.match(suggested,/<button class="btn primary" data-action="confirm-suggestion"/);
  assert.match(suggested,/<button class="btn" type="submit" aria-label="送出描述">/);
  assert.equal((suggested.match(/class="btn primary"/g)||[]).length,1);
});
