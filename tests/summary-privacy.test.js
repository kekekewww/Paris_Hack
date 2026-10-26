import test from 'node:test';
import assert from 'node:assert/strict';
import {guided,workspace,shell} from '../src/components.js';

test('模型送出前明示必要對話及案件摘要外送，原檔與OCR仍不外送',()=>{
  const health={llm_provider:'openai_compatible',llm_configured:true,llm_verified:false};
  const c={id:'synthetic',claim_type_id:'inpatient',documents:[],conditions:{},messages:[]};
  for(const html of [guided(null,'api',{health}),workspace(c,true,'api','',health)]){
    assert.match(html,/必要對話與案件摘要會送至 OpenRouter 與模型供應商/);
    assert.match(html,/上傳文件與 OCR 不外送模型/);
  }
  const disclosure=shell('',{mode:'api',health});
  assert.match(disclosure,/<details class="service-info">[\s\S]*關係、就醫日期、診斷／術名及商品資料[\s\S]*<\/details>/);
  assert.doesNotMatch(shell('',{mode:'mock'}),/案件摘要會送至 OpenRouter/);
});
