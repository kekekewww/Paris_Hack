import test from 'node:test';
import assert from 'node:assert/strict';
import * as ui from '../src/components.js';

const source='https://life.cardif.com.tw/zh/a314';
const doc=(id,extra={})=>({id,title:id,description:'合成文件',requirement_type:'required',applicability:true,status:'not_started',official_url:source,confirmed_findings:[],...extra});
const caseOf=documents=>({id:'test',revision:3,claim_type_id:'inpatient',conditions:{},documents,messages:[]});
test('人工核對備妥有獨立完成出口，原辨識提醒保留',()=>{
  assert.equal(ui.isReady(doc('a',{status:'manual_ready'})),true);
  const html=ui.analysisResult(doc('a',{confirmed_findings:['f'],analysis:{id:'analysis',findings:[{id:'f',message:'簽名需核對'}]}}),'mock');
  assert.match(html,/data-action="manual-ready"/);
  assert.match(html,/簽名需核對/);
});
test('移除參考信心百分比且沒有原檔時不畫定位框',()=>{
  const html=ui.analysisResult(doc('a',{analysis:{id:'a',confidence:.99,provider:'pdf_text',findings:[{id:'f'}],bounding_boxes:[{finding_id:'f',x:.1,y:.1,width:.2,height:.2}]}}),'api');
  assert.doesNotMatch(html,/99%|參考信心|class="marker"/);
  assert.match(html,/重新選取/);
});
test('官方同URL只出現一次，頁碼與用途仍可核對',()=>{
  const html=ui.docCard(doc('a',{download_url:source,source_references:[{title:'官方條件',official_url:source,page_number:2}]}));
  assert.equal((html.match(new RegExp(`href="${source}"`,'g'))||[]).length,1);
  assert.match(html,/第 2 頁/);
  assert.match(html,/官方空白表單/);
});
test('清單與摘要共用必要性排序，適用與準備各自呈現',()=>{
  const c=caseOf([doc('不適用',{requirement_type:'conditional',applicability:false,status:'not_applicable'}),doc('待確認',{requirement_type:'conditional',applicability:null}),doc('適用條件',{requirement_type:'conditional'}),doc('必備')]);
  const workspace=ui.workspace(c,false,'mock');
  assert.deepEqual([...workspace.matchAll(/data-document-id="([^"]+)"/g)].map(m=>m[1]),['必備','適用條件','待確認','不適用']);
  const summary=ui.summary(c,{official_url:source});
  assert.deepEqual([...summary.matchAll(/<tr><td>([^<]+)<(?:div|\/td)>/g)].map(m=>m[1]),['必備','適用條件','待確認','不適用']);
  assert.match(ui.docCard(doc('a',{requirement_type:'conditional'})),/確認需要/);
});
test('待答欄位提供單題快速答覆，工作區提案有差異確認取消',()=>{
  const c=caseOf([]);c.dialogue_state={pending_question:{field:'surgery',prompt:'是否手術？',options:[{value:'yes',label:'有'},{value:'no',label:'沒有'},{value:'unknown',label:'尚不確定'}]}};
  c.messages=[{role:'assistant',content:'是否手術？',response:{proposal:{id:'p',base_revision:3,changes:[{field:'conditions.surgery',before:'no',after:'yes'}]}}}];
  const html=ui.workspace(c,true,'mock');
  assert.match(html,/data-action="quick-answer"/);
  assert.match(html,/data-action="accept-proposal"/);
  assert.match(html,/data-action="reject-proposal"/);
  assert.match(html,/手術/);
});
test('案件摘要保留關係、部分日期與多商品未驗證版本',()=>{
  const c=caseOf([]);c.details={insured_relation:'parent',diagnosis_name:'合成診斷',surgery_name:'合成術名',surgery_date:'10/3',visit_dates:{admission:'10/2',discharge_pending:true},policy_products:[{code:'AAA',version:'2025',verification_status:'unverified'},{code:'BBB',version:null,verification_status:'unverified'}]};
  const html=ui.summary(c,{official_url:source});
  for(const label of ['父母','合成診斷','10/2','10/3','AAA','BBB','2025','待查證'])assert.ok(html.includes(label),label);
});
test('非首次重大疾病病理仍待官方病況確認，不能標成已確認免附',()=>{
  const pathology=doc('pathology',{requirement_type:'conditional',applicability:false,review_required:true,status:'not_started'});
  const html=ui.docCard(pathology);
  assert.match(html,/適用條件待確認/);
  assert.doesNotMatch(html,/<span class="applicability">已確認不適用/);
  assert.deepEqual(ui.filterDocuments([pathology],'','confirm').map(d=>d.id),['pathology']);
  assert.deepEqual(ui.sortDocuments([doc('不適用',{applicability:false,status:'not_applicable'}),pathology,doc('適用',{requirement_type:'conditional',applicability:true})]).map(d=>d.id),['適用','pathology','不適用']);
  assert.equal(ui.isReady(pathology),false);
});
test('聊天後仍可檢視同revision有效提案，舊revision不可重套',()=>{
  const c=caseOf([]);const proposal={id:'p',base_revision:3,changes:[{field:'conditions.surgery',before:'no',after:'yes'}]};
  c.dialogue_state={active_proposal:proposal,pending_question:{kind:'proposal'}};
  c.messages=[{role:'assistant',content:'請按確認按鈕'}];
  assert.equal(ui.currentProposal(c)?.id,'p');
  c.revision=4;
  assert.equal(ui.currentProposal(c),null);
});
test('有原檔仍須具備真實定位座標，不以預設框代替缺失位置',()=>{
  const html=ui.analysisResult(doc('a',{analysis:{analysis_id:'a',provider:'pdf_text',findings:[{id:'f'}],bounding_boxes:[{finding_id:'f',bounding_box:null},{finding_id:'f',location_status:'unlocated',x:.1,y:.2,width:.3,height:.1}]}}),'api','blob:synthetic','image/png');
  assert.doesNotMatch(html,/class="marker"/);
});
