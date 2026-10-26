import test from 'node:test';
import assert from 'node:assert/strict';
import {analysisResult} from '../src/components.js';

const box=page_number=>({page_number,x:.1,y:.2,width:.3,height:.1});
function render(findings,boxes,page=1){return analysisResult({id:'application',title:'合成申請書',confirmed_findings:[],analysis:{analysis_id:'synthetic',provider:'pdf_text',findings,bounding_boxes:boxes}},'api','blob:synthetic','application/pdf',{ready:true,pageNumber:page,pageCount:2})}
const targets=html=>[...html.matchAll(/class="marker"[^>]*data-finding="([^"]+)"/g)].map(match=>match[1]);

test('未定位提醒在前時，唯一定位框仍連到自身有位置的提醒',()=>{
  const located=box(1);
  const html=render([{id:'unlocated-first',bounding_box:null,location_status:'unlocated'},{id:'located-second',bounding_box:located,location_status:'label'}],[located]);
  assert.deepEqual(targets(html),['located-second']);
  assert.match(html,/data-finding="located-second"[^>]*aria-label="查看欄位提醒 2"/);
});
test('相同座標位於不同頁時，以各提醒自己的頁碼和ID關聯',()=>{
  const first=box(1),second=box(2);
  const findings=[{id:'no-box',bounding_box:null,location_status:'unlocated'},{id:'page-two',page_number:2,bounding_box:second,location_status:'label'},{id:'page-one',page_number:1,bounding_box:first,location_status:'label'}];
  // 頂層清單順序不必與提醒相同，不得用順序配對。
  assert.deepEqual(targets(render(findings,[first,second],1)),['page-one']);
  assert.deepEqual(targets(render(findings,[first,second],2)),['page-two']);
});
test('沒有明確關聯的頂層座標不產生定位框，明確ID可安全支援舊格式',()=>{
  assert.deepEqual(targets(render([{id:'missing-association'}],[box(1)])),[]);
  assert.deepEqual(targets(render([{id:'explicit'}],[{...box(1),finding_id:'explicit'}])),['explicit']);
});
test('頁面提示、未定位或空座標皆不能生成精確定位框',()=>{
  const findings=[{id:'page',bounding_box:box(1),location_status:'page'},{id:'null',bounding_box:null,location_status:'label'},{id:'unlocated',bounding_box:box(1),location_status:'unlocated'},{id:'valid',bounding_box:box(1),location_status:'label'}];
  assert.deepEqual(targets(render(findings,[box(1)])),['valid']);
});
