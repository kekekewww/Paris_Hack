import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

// 執行實際頁面載入函式；控制服務完成時機以重現使用者途中離頁。
const source=await readFile(new URL('../src/app.js',import.meta.url),'utf8');
const loaders=source.slice(source.indexOf('async function loadLibrary(){'),source.indexOf('function readDetails('));
function makeLoaders(state,service,errors){return new Function('state','service','render','showError',`let libraryLoading=false,faqLoading=false;${loaders};return {loadLibrary,loadFaq}`)(state,service,()=>{},error=>errors.push(error.message))}
for(const kind of ['Library','Faq'])test(`${kind}請求失敗不污染離開後的工作區，錯誤保留在其資源狀態`,async()=>{
  let reject;const error=new Error('合成頁面故障');
  const state={route:kind==='Library'?'library':'faq',libraryQuery:'',libraryCategory:'all'};
  const errors=[];
  const service={[`get${kind}`]:()=>new Promise((_,fail)=>{reject=fail})};
  const work=makeLoaders(state,service,errors)[`load${kind}`]();
  state.route='workspace';reject(error);await work;
  assert.deepEqual(errors,[]);
  assert.equal(state[kind==='Library'?'libraryError':'faqError'],error);
});
test('同分頁恢復原檔後可直接重分析，不被空的原生選檔欄位擋住',()=>{
  const sync=source.slice(source.indexOf('function syncUploadButton(){'),source.indexOf('async function selectFile('));
  const button={disabled:true},input={required:true};
  const document={querySelector:selector=>selector==='#document-file'?input:button};
  new Function('document','state','fileChecking','currentFile',`${sync};syncUploadButton()`)(document,{busy:false},false,{name:'synthetic.png'});
  assert.equal(button.disabled,false);
  assert.equal(input.required,false);
});
