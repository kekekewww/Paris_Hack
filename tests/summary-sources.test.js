import test from 'node:test';
import assert from 'node:assert/strict';
import {summary} from '../src/components.js';

const common='https://life.cardif.com.tw/zh/a314';
const form='https://life.cardif.com.tw/documents/claim.pdf';
const example='https://life.cardif.com.tw/documents/claim-example.pdf';
const source={title:'官方理賠資訊',official_url:common,submission:{postal:{address:'合成送件地址',recipient:'合成理賠部'},support:{phone:'0800-DEMO',hours:'展示時段'}}};
const document=(id,extra={})=>({id,title:`合成文件${id}`,requirement_type:'required',status:'not_started',official_url:common,source_references:[],...extra});
const caseWith=documents=>({claim_type_id:'inpatient',conditions:{},documents});
const urls=html=>[...html.matchAll(/href="([^"]+)"/g)].map(match=>match[1]);

test('摘要移除逐列官方連結，共同a314與送件入口合併一次，PDF用途及頁碼不遺失',()=>{
  const html=summary(caseWith([
    document('A',{download_url:form,example_url:example,source_references:[{title:'保險金申請書',official_url:form,page_number:1},{title:'官方理賠資訊',official_url:common}]}),
    document('B',{download_url:form,source_references:[{title:'保險金申請書',official_url:form,page_number:2},{title:'填寫範例',official_url:example,page_number:3}]}),
  ]),source);
  const hrefs=urls(html);
  for(const url of [common,form,example])assert.equal(hrefs.filter(href=>href===url).length,1,url);
  assert.doesNotMatch(html.match(/<tbody>([\s\S]*?)<\/tbody>/)?.[1]||'',/<a\b/);
  for(const text of ['保險金申請書','空白表單','填寫範例','第 1 頁','第 2 頁','第 3 頁','官方理賠資訊','合成送件地址'])assert.ok(html.includes(text),text);
  const submission=html.slice(html.indexOf('下一步：依官方方式送件'));
  assert.ok(urls(submission).includes(common),'共用a314保留在官方送件情境');
});
test('摘要依完整URL去重，不因同網域或同檔名合併不同官方版本',()=>{
  const first=form+'?version=1',second=form+'?version=2';
  const html=summary(caseWith([document('A',{official_url:first}),document('B',{official_url:second}),document('C',{official_url:'https://evil.test/not-official.pdf'})]),source);
  for(const url of [first,second])assert.equal(urls(html).filter(href=>href===url).length,1);
  assert.doesNotMatch(html,/href="https:\/\/evil/);
});
test('沒有獨立引用標題的下載與範例仍帶文件名稱，避免集中後只剩模糊用途',()=>{
  const html=summary(caseWith([document('A',{download_url:form,example_url:example})]),source);
  assert.match(html,new RegExp(`href="${form}"[^>]*>[^<]*合成文件A[^<]*空白表單`));
  assert.match(html,new RegExp(`href="${example}"[^>]*>[^<]*合成文件A[^<]*填寫範例`));
});
test('集中來源後仍保留摘要狀態、準備計數與下載列印操作',()=>{
  const html=summary(caseWith([document('A',{status:'manual_ready',analysis:{findings:[{id:'f'}]}}),document('B')]),source);
  for(const text of ['已人工核對並備妥','原辨識結果保留','尚未準備','仍需確認的條件','下載摘要','列印摘要','返回工作區'])assert.ok(html.includes(text),text);
  assert.equal((html.match(/<strong>1<\/strong>/g)||[]).length,2);
  assert.equal(urls(html).filter(url=>url===common).length,1);
});
test('集中引用仍保留用途與頁碼配對，且來源可直接列印',()=>{
  const html=summary(caseWith([document('A',{source_references:[{title:'簽署說明',official_url:form,page_number:1},{title:'匯款說明',official_url:form,page_number:2}]})]),source);
  assert.match(html,/簽署說明 · 第 1 頁/);
  assert.match(html,/匯款說明 · 第 2 頁/);
  assert.doesNotMatch(html,/<details[^>]*summary-sources/);
});
test('同URL的完整相同標題與用途前綴只顯示一次',()=>{
  for(const [index,title] of ['保險金申請書','病歷資料調閱授權書'].entries()){
    const url=form+'?doc='+index;
    const html=summary(caseWith([document('A',{title,official_url:url,download_url:url,source_references:[{title,official_url:url}]})]),source);
    const label=[...html.matchAll(/<a href="([^"]+)"[^>]*>([^<]*)<\/a>/g)].find(match=>match[1]===url)?.[2];
    assert.equal(label,title+' · 空白表單 ↗');
    assert.equal(urls(html).filter(href=>href===url).length,1);
  }
});
test('用途標籤精簡不吞不同完整標題或頁碼引用',()=>{
  const title='保險金申請書';
  const html=summary(caseWith([document('A',{title,official_url:form,download_url:form,source_references:[{title,official_url:form},{title:title+'附表',official_url:form},{title:'簽署說明',official_url:form,page_number:1},{title:'匯款說明',official_url:form,page_number:2}]})]),source);
  const label=[...html.matchAll(/<a href="([^"]+)"[^>]*>([^<]*)<\/a>/g)].find(match=>match[1]===form)?.[2];
  for(const text of [title+'附表',title+' · 空白表單','簽署說明 · 第 1 頁','匯款說明 · 第 2 頁'])assert.ok(label.includes(text),text);
  assert.ok(!label.includes(title+' · '+title+' · 空白表單'));
});
