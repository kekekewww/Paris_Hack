import test from 'node:test';
import assert from 'node:assert/strict';
import {guidedConfirmationPayload} from '../src/guided-confirmation.js';

const response = {proposal:{id:'server-proposal',base_revision:4},proposed_case_updates:{claim_type_id:'inpatient',conditions:{cause:'illness',surgery:'yes'},details:{insured_relation:'parent'}}};
const item = {id:'case',revision:4,details:{},dialogue_state:{active_proposal:{id:'server-proposal',base_revision:4}}};

test('獨立選取原建議後建立清單使用當前伺服器提案，保留已驗證對話事實',()=>{
  assert.deepEqual(guidedConfirmationPayload(item,response,'inpatient'),{
    proposal_id:'server-proposal',expected_revision:4,proposal_action:'accept',
  });
});
test('選擇其他類型仍提交明確選擇，不接受原類型的提案',()=>{
  assert.deepEqual(guidedConfirmationPayload(item,response,'outpatient'),{
    claim_type_id:'outpatient',conditions:{cause:'illness',surgery:'yes'},details:{insured_relation:'parent'},expected_revision:4,
  });
});
for(const current of [
  {...item,revision:5},
  {...item,dialogue_state:{active_proposal:{id:'other',base_revision:4}}},
  {...item,dialogue_state:{active_proposal:null}},
])test('舊版本或失效提案不可作為接受操作 '+JSON.stringify(current),()=>{
  const payload=guidedConfirmationPayload(current,response,'inpatient');
  assert.equal(payload.proposal_id,undefined);
  assert.equal(payload.expected_revision,current.revision);
  assert.equal(payload.claim_type_id,'inpatient');
});
