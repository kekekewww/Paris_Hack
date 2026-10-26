import test from 'node:test';
import assert from 'node:assert/strict';
import {MockClaimService} from '../src/services/mock-claim-service.js';

const service=()=>new MockClaimService({delay:0,storage:null});
const direct=s=>s.createCase({entry_path:'direct',claim_type_id:'inpatient',conditions:{cause:'illness',surgery:'no'}});
const file=()=>new File(['%PDF-1.4 synthetic'],'demo.pdf',{type:'application/pdf'});

test('mock single pending question accepts a short answer without inventing other facts',async()=>{
  const s=service(),c=await s.createCase({entry_path:'guided'});
  const first=await s.sendMessage(c.id,'媽媽住院三天');
  assert.equal(first.response.response_type,'clarification');
  assert.equal(first.response.pending_question.field,'cause');
  assert.deepEqual(first.response.suggested_claim_types,[]);
  const second=await s.sendMessage(c.id,'疾病');
  assert.equal(second.response.pending_question.field,'surgery');
  const third=await s.sendMessage(c.id,'有');
  assert.equal(third.case.dialogue_state.facts.surgery,'yes');
  assert.equal(third.case.claim_type_id,null);
  assert.equal(third.response.pending_question.field,'payment_method');
  const final=await s.sendMessage(c.id,'不知道，稍後確認');
  assert.equal(final.response.proposed_case_updates.conditions.cause,'illness');
});

test('mock unknown is deferred and is not repeatedly asked',async()=>{
  const s=service(),c=await s.createCase({entry_path:'guided'});
  await s.sendMessage(c.id,'住院三天');
  const result=await s.sendMessage(c.id,'不知道，稍後確認');
  assert.ok(result.case.dialogue_state.deferred_fields.includes('cause'));
  assert.notEqual(result.response.pending_question?.field,'cause');
});

test('mock workspace proposal applies only through revision checked acceptance',async()=>{
  const s=service(),c=await direct(s);
  const proposed=await s.sendMessage(c.id,'更正，這次有手術');
  assert.equal(proposed.case.conditions.surgery,'no');
  assert.equal(proposed.case.revision,c.revision+1);
  assert.equal(proposed.response.proposal.base_revision,proposed.case.revision);
  assert.ok(proposed.response.proposal.changes.some(change=>change.field==='conditions.surgery'));
  const patch={expected_revision:proposed.case.revision,proposal_id:proposed.response.proposal.id,proposal_action:'accept'};
  const accepted=await s.updateCase(c.id,patch);
  assert.equal(accepted.conditions.surgery,'yes');
  await assert.rejects(s.updateCase(c.id,patch),error=>error.status===409);
});

test('mock rejecting a proposal preserves known case facts',async()=>{
  const s=service(),c=await direct(s),r=await s.sendMessage(c.id,'更正，有手術');
  const rejected=await s.updateCase(c.id,{expected_revision:r.case.revision,proposal_id:r.response.proposal.id,proposal_action:'reject'});
  assert.equal(rejected.conditions.surgery,'no');
  assert.deepEqual(rejected.dialogue_state.facts,c.dialogue_state.facts);
  assert.equal(rejected.dialogue_state.pending_question,null);
});

test('mock proposal short denial asks for a correction without negating known admission',async()=>{
  const s=service(),c=await direct(s);await s.sendMessage(c.id,'更正，有手術');
  const result=await s.sendMessage(c.id,'不是');
  assert.equal(result.response.response_type,'clarification');
  assert.match(result.response.message,/哪|更正|不符/);
  assert.equal(result.case.dialogue_state.facts.inpatient,'yes');
  assert.equal(result.case.conditions.surgery,'no');
});

test('mock proposal short approval preserves the explicit confirmation action without applying it',async()=>{
  const s=service(),c=await direct(s),proposed=await s.sendMessage(c.id,'更正，有手術');
  const result=await s.sendMessage(c.id,'是');
  assert.equal(result.case.conditions.surgery,'no');
  assert.equal(result.case.revision,proposed.case.revision+1);
  assert.notEqual(result.response.proposal.id,proposed.response.proposal.id);
  assert.equal(result.response.proposal.base_revision,result.case.revision);
  assert.match(result.response.message,/確認|取消/);
  assert.ok(result.case.dialogue_state.active_proposal);
  await assert.rejects(s.updateCase(c.id,{expected_revision:proposed.case.revision,proposal_id:proposed.response.proposal.id,proposal_action:'accept'}),error=>error.status===409);
  await assert.rejects(s.updateCase(c.id,{expected_revision:result.case.revision,proposal_id:proposed.response.proposal.id,proposal_action:'accept'}),error=>error.status===409);
  assert.equal((await s.getCase(c.id)).conditions.surgery,'no');
  const accepted=await s.updateCase(c.id,{expected_revision:result.case.revision,proposal_id:result.response.proposal.id,proposal_action:'accept'});
  assert.equal(accepted.conditions.surgery,'yes');
  assert.equal(accepted.revision,result.case.revision+1);
});

test('mock an unrelated document question preserves the active proposal acceptance action',async()=>{
  const s=service(),c=await direct(s),r=await s.sendMessage(c.id,'更正，有手術');
  const question=await s.sendMessage(c.id,'申請書要簽名嗎？');
  assert.equal(question.response.response_type,'case_update_proposal');
  assert.equal(question.case.conditions.surgery,'no');
  assert.equal(question.case.revision,r.case.revision+1);
  assert.notEqual(question.response.proposal.id,r.response.proposal.id);
  await assert.rejects(s.updateCase(c.id,{expected_revision:question.case.revision,proposal_id:r.response.proposal.id,proposal_action:'accept'}),error=>error.status===409);
  const accepted=await s.updateCase(c.id,{expected_revision:question.case.revision,proposal_id:question.response.proposal.id,proposal_action:'accept'});
  assert.equal(accepted.conditions.surgery,'yes');
});

test('mock document writes invalidate proposals and a new acknowledgement creates a current one-use proposal',async()=>{
  const s=service(),c=await direct(s),r=await s.sendMessage(c.id,'更正，有手術');
  const written=await s.updateDocument(c.id,'application',{status:'uploaded'});
  assert.equal(written.revision,r.case.revision+1);
  assert.equal(written.dialogue_state.active_proposal,null);
  assert.equal(written.dialogue_state.pending_question.kind,'fact');
  await assert.rejects(s.updateCase(c.id,{expected_revision:written.revision,proposal_id:r.response.proposal.id,proposal_action:'accept'}),e=>e.status===409);
  const fresh=await s.sendMessage(c.id,'是');
  assert.equal(fresh.case.conditions.surgery,'no');
  assert.equal(fresh.case.revision,written.revision+1);
  assert.notEqual(fresh.response.proposal.id,r.response.proposal.id);
  assert.equal(fresh.response.proposal.base_revision,fresh.case.revision);
  const accepted=await s.updateCase(c.id,{expected_revision:fresh.case.revision,proposal_id:fresh.response.proposal.id,proposal_action:'accept'});
  assert.equal(accepted.conditions.surgery,'yes');
});

test('mock successful saves increment once while reads and rejected writes keep the current revision',async()=>{
  const s=service(),c=await s.createCase({entry_path:'guided'});
  assert.equal(c.revision,0);
  const r=await s.sendMessage(c.id,'你好');
  assert.equal(r.case.revision,1);
  assert.equal((await s.getCase(c.id)).revision,1);
  s.simulateFailure();await assert.rejects(s.sendMessage(c.id,'住院三天'));
  assert.equal((await s.getCase(c.id)).revision,1);
  const directCase=await direct(s),analyzed=await s.analyzeDocument(directCase.id,'application',file());
  assert.equal(analyzed.revision,1);
  await assert.rejects(s.updateDocument(directCase.id,'application',{status:'precheck_passed'}));
  assert.equal((await s.getCase(directCase.id)).revision,1);
});

for(const legacyState of ['absent','missing-active'])test(`mock saved legacy case ${legacyState} receives current schema defaults before messaging`,async()=>{
  const original=await direct(service()),legacy=structuredClone(original);
  if(legacyState==='absent')delete legacy.dialogue_state;
  else legacy.dialogue_state={facts:{cause:'illness',surgery:'no'},pending_question:null,deferred_fields:[]};
  const saved=JSON.stringify({[legacy.id]:legacy});
  const restored=new MockClaimService({delay:0,storage:{getItem:()=>saved,setItem(){}}});
  const result=await restored.sendMessage(legacy.id,'申請書要簽名嗎？');
  assert.equal(result.case.revision,original.revision+1);
  assert.equal(result.case.claim_type_id,original.claim_type_id);
  assert.deepEqual(result.case.conditions,original.conditions);
  assert.equal(result.case.dialogue_state.active_proposal,null);
  assert.deepEqual(result.case.dialogue_state.conditions,original.conditions);
  assert.deepEqual(result.case.dialogue_state.details,original.details);
  assert.equal(result.case.dialogue_state.facts.inpatient,'unknown');
  if(legacyState==='missing-active')assert.equal(result.case.dialogue_state.facts.surgery,'no');
  assert.match(result.response.message,/簽名/);
});

test('mock case detail corrections preserve multiple unverified product references',async()=>{
  const s=service(),c=await direct(s),r=await s.sendMessage(c.id,'更正，是媽媽，診斷為肺炎，保單商品 IHI_C_1131001、IHO_1131001');
  assert.equal(r.case.details.insured_relation,'unknown');
  assert.equal(r.response.proposed_case_updates.details.insured_relation,'parent');
  assert.equal(r.response.proposed_case_updates.details.diagnosis_name,'肺炎');
  assert.equal(r.response.proposed_case_updates.details.policy_products.length,2);
  assert.ok(r.response.proposed_case_updates.details.policy_products.every(p=>p.verification_status==='unverified'));
});

test('mock manual case edits seed subsequent corrections from the current confirmed details and class',async()=>{
  const s=service(),c=await s.createCase({entry_path:'direct',claim_type_id:'inpatient',conditions:{cause:'illness',surgery:'no'},details:{insured_relation:'parent',policy_products:[{code:'IHI_C_1131001',version:null,verification_status:'unverified'}]}});
  const changed=await s.updateCase(c.id,{claim_type_id:'outpatient',expected_revision:c.revision});
  const proposed=await s.sendMessage(c.id,'更正，有手術');
  assert.equal(proposed.response.proposed_case_updates.claim_type_id,'outpatient');
  assert.equal(proposed.response.proposed_case_updates.details.insured_relation,'parent');
  assert.equal(proposed.response.proposed_case_updates.details.policy_products.length,1);
  assert.equal(changed.dialogue_state.facts.inpatient,'unknown');
});

test('mock confirmed condition edits supersede old guided drafts in later proposals',async()=>{
  const s=service(),c=await s.createCase({entry_path:'guided'});
  await s.sendMessage(c.id,'住院三天');await s.sendMessage(c.id,'疾病');await s.sendMessage(c.id,'沒有');
  const r=await s.sendMessage(c.id,'直接匯款');
  await s.updateCase(c.id,r.response.proposed_case_updates);
  await s.updateCase(c.id,{conditions:{payment_method:'other'}});
  const correction=await s.sendMessage(c.id,'更正，有手術');
  assert.equal(correction.response.proposed_case_updates.conditions.payment_method,'other');
  assert.ok(!correction.response.proposal.changes.some(change=>change.field==='conditions.payment_method'));
});

test('mock explicit uncertainty proposes unknown without changing confirmed facts before acceptance',async()=>{
  const s=service(),c=await s.createCase({entry_path:'direct',claim_type_id:'inpatient',conditions:{cause:'illness',surgery:'yes'}});
  const r=await s.sendMessage(c.id,'更正，手術還不確定');
  assert.equal(r.response.proposed_case_updates.conditions.surgery,'unknown');
  assert.equal(r.case.conditions.surgery,'yes');
  assert.equal(r.case.dialogue_state.facts.surgery,'yes');
  const changed=await s.updateCase(c.id,{expected_revision:r.case.revision,proposal_id:r.response.proposal.id,proposal_action:'accept'});
  assert.equal(changed.conditions.surgery,'unknown');
  assert.equal(changed.conditions.cause,'illness');
});

test('mock withdrawing the only care setting asks one followup and changes class only after acceptance',async()=>{
  const s=service(),c=await direct(s);
  const first=await s.sendMessage(c.id,'更正，沒有住院');
  assert.equal(first.response.response_type,'clarification');
  assert.equal(first.response.pending_question.field,'outpatient');
  assert.equal(first.case.claim_type_id,'inpatient');
  assert.deepEqual(first.case.conditions,c.conditions);
  assert.equal(first.case.dialogue_state.facts.outpatient,'unknown');
  assert.equal(first.case.dialogue_state.facts.emergency,'unknown');
  const second=await s.sendMessage(c.id,'有');
  assert.equal(second.response.proposed_case_updates.claim_type_id,'outpatient');
  assert.equal(second.case.claim_type_id,'inpatient');
  const rejected=await s.updateCase(c.id,{expected_revision:second.case.revision,proposal_id:second.response.proposal.id,proposal_action:'reject'});
  assert.equal(rejected.claim_type_id,'inpatient');
  assert.deepEqual(rejected.conditions,c.conditions);
  const again=await s.sendMessage(c.id,'更正，只有門診，沒有住院');
  const accepted=await s.updateCase(c.id,{expected_revision:again.case.revision,proposal_id:again.response.proposal.id,proposal_action:'accept'});
  assert.equal(accepted.claim_type_id,'outpatient');
  assert.equal(accepted.dialogue_state.facts.inpatient,'no');
});

test('mock manual ready retains OCR findings and is revoked by reanalysis',async()=>{
  const s=service(),c=await direct(s),r=await s.analyzeDocument(c.id,'application',file());
  const doc=r.documents.find(d=>d.id==='application'),analysisId=doc.analysis.analysis_id;
  await assert.rejects(s.updateDocument(c.id,'application',{status:'manual_ready',analysis_id:analysisId}),e=>e.code==='FINDINGS_NOT_CONFIRMED');
  await s.updateDocument(c.id,'application',{analysis_id:analysisId,confirmed_findings:doc.analysis.findings.map(f=>f.id)});
  const ready=await s.updateDocument(c.id,'application',{status:'manual_ready',analysis_id:analysisId});
  assert.equal(ready.documents.find(d=>d.id==='application').status,'manual_ready');
  assert.deepEqual(ready.documents.find(d=>d.id==='application').analysis,doc.analysis);
  const fresh=await s.analyzeDocument(c.id,'application',file());
  assert.equal(fresh.documents.find(d=>d.id==='application').status,'needs_attention');
  assert.deepEqual(fresh.documents.find(d=>d.id==='application').confirmed_findings,[]);
  await assert.rejects(s.updateDocument(c.id,'application',{analysis_id:analysisId,confirmed_findings:[]}),e=>e.status===409);
});

test('mock official library and FAQ use only the same verified catalog with exact product uncertainty',async()=>{
  const s=service(),all=await s.getLibrary();
  assert.equal(all.total,all.documents.length);
  assert.ok(all.total>0);
  assert.equal(new Set(all.documents.map(d=>d.id)).size,all.total);
  const selected=await s.getLibrary({query:'申請',category:'claims'});
  assert.ok(selected.documents.length>0);
  assert.ok(selected.documents.every(d=>d.category_id==='claims'&&`${d.title} ${d.category_label}`.includes('申請')));
  const faq=await s.getFaq();
  assert.ok(faq.length>0);
  assert.ok(faq.every(q=>q.sources.length&&q.sources.every(source=>source.official_url.startsWith('https://life.cardif.com.tw/'))));
  const product=await s.getProduct('IHI_C_1131001');
  assert.equal(product.verification_status,'unverified');
  assert.deepEqual(product.versions,[]);
  assert.ok(product.candidate_sources.length>0);
  assert.deepEqual((await s.getProduct('FAKE_999')).candidate_sources,[]);
});
