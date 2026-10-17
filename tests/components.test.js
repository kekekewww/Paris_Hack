import test from 'node:test';
import assert from 'node:assert/strict';
import {officialUrl,sourceLink,summary,isReady,docCard,analysisResult} from '../src/components.js';

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
