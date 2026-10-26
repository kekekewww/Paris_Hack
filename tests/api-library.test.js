import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiClaimService} from '../src/services/api-claim-service.js';
import {libraryPage,faqPage} from '../src/components.js';

test('官方文件／FAQ／商品查詢使用相同來源API與編碼參數',async()=>{
  const requests=[];
  const service=new ApiClaimService({fetchImpl:async(path)=>{requests.push(path);return Response.json({})}});
  await service.getLibrary({query:'申請書 & ABC',category:'medical claims'});
  await service.getFaq();
  await service.getProduct('AAA/2025');
  const query=new URL(requests[0],'https://demo.invalid');
  assert.equal(query.pathname,'/api/v1/library');
  assert.equal(query.searchParams.get('query'),'申請書 & ABC');
  assert.equal(query.searchParams.get('category'),'medical claims');
  assert.equal(requests[1],'/api/v1/faq');
  assert.equal(requests[2],'/api/v1/products/AAA%2F2025');
});
test('官方文件庫僅顯示服務實際筆數並阻止不受信任連結與HTML',()=>{
  const data={total:1,scope_note:'已查核',categories:[{id:'x',label:'其他',document_count:1,preparation_supported:false}],documents:[{id:'d',title:'<script>bad</script>',category_id:'x',category_label:'其他',document_type:'文件',official_url:'https://evil.test/form.pdf'}]};
  const html=libraryPage(data);
  assert.match(html,/共 1 筆/);
  assert.match(html,/目前提供文件查詢/);
  assert.doesNotMatch(html,/href="https:\/\/evil|<script>/);
  assert.match(html,/&lt;script&gt;/);
  assert.match(faqPage([{question:'問題',answer:'<img src=x>',sources:[]}]),/&lt;img/);
});
