import officialRegistry from '../../data/official-sources.json' with { type: 'json' };
import { ServiceError } from './service-error.js';
let libraryPromise;
const loadOfficialLibrary=()=>libraryPromise??=import('./official-library-data.js').then(module=>module.default);

const STORAGE_KEY = 'cardif-claim-demo-cases-v1';
const MAX_BYTES = 10 * 1024 * 1024;
const DEFAULT_CONDITIONS = { cause: 'unknown', surgery: 'unknown', receipt_type: 'unknown', payment_method: 'unknown', first_claim: 'unknown', diagnosis_has_surgery_details: 'unknown' };
const emptyDetails = () => ({ insured_relation: 'unknown', diagnosis_name: null, surgery_name: null, surgery_date: null, visit_dates: { admission: null, discharge: null, visit: null, discharge_pending: false }, policy_products: [], deferred_fields: [] });
const emptyFacts = () => Object.fromEntries(['cause','inpatient','outpatient','emergency','critical_diagnosis','surgery'].map(field => [field,'unknown']));
const copy = value => JSON.parse(JSON.stringify(value));
const identifier = () => globalThis.crypto?.randomUUID?.() ?? `demo-${Date.now()}-${Math.random().toString(36).slice(2)}`;
const now = () => new Date().toISOString();
const fail = (code, message, status = 422) => { throw new ServiceError(code, message, status); };

function browserStorage() {
  try { return globalThis.sessionStorage ?? null; } catch { return null; }
}

function validateConditions(conditions = {}) {
  const answers = ['unknown', 'yes', 'no'];
  const options = { cause: ['unknown', 'accident', 'illness'], surgery: answers, receipt_type: ['unknown', 'actual', 'daily'], payment_method: ['unknown', 'remittance', 'other'], first_claim: answers, diagnosis_has_surgery_details: answers, pathology_required_for_condition: answers, insurer_requested_medical_authorization: answers, insurer_requested_nhi_request: answers };
  if (!conditions || typeof conditions !== 'object' || Array.isArray(conditions)) fail('VALIDATION_ERROR', '案件條件格式不正確。');
  for (const [field, value] of Object.entries(conditions)) {
    if (!options[field] || !options[field].includes(value)) fail('VALIDATION_ERROR', '案件條件包含無效選項。');
  }
  return conditions;
}

function evaluateCondition(condition, conditions) {
  if (condition.op === 'always') return true;
  if (condition.all) {
    const values = condition.all.map(item => evaluateCondition(item, conditions));
    return values.includes(false) ? false : values.includes(null) ? null : true;
  }
  const field = condition.field;
  let value = field === 'had_surgery'
    ? conditions.surgery === 'yes' ? true : conditions.surgery === 'no' ? false : undefined
    : conditions[field];
  if (typeof condition.equals === 'boolean') value = value === 'yes' ? true : value === 'no' ? false : value;
  if (value === undefined || value === 'unknown') return null;
  return value === condition.equals;
}

function sourceFor(registry, id, pageNumber = null) {
  const source = registry.sources.find(item => item.source_id === id);
  if (!source) fail('SOURCE_NOT_FOUND', '找不到已查核的官方來源。', 404);
  const url = new URL(source.official_url);
  if (url.protocol !== 'https:' || url.hostname !== 'life.cardif.com.tw') fail('INVALID_SOURCE', '官方來源網址未通過安全檢查。');
  return { ...source, page_number: pageNumber ?? source.page_number };
}

function buildChecklist(registry, item, previous = []) {
  if (!item.claim_type_id) return [];
  return registry.rules.filter(rule => rule.claim_type_id === item.claim_type_id).map(rule => {
    const definition = registry.documents.find(doc => doc.document_id === rule.document_id);
    if (!definition) fail('INVALID_REGISTRY', '官方文件索引缺少規則所引用的文件。');
    const source = sourceFor(registry, rule.source_id, rule.page_number);
    const download = definition.download_source_id ? sourceFor(registry, definition.download_source_id) : null;
    const example = definition.example_source_ids.map(id => sourceFor(registry, id)).find(entry => entry.related_claim_types.includes(item.claim_type_id));
    const applicability = evaluateCondition(rule.condition, item.conditions);
    const old = previous.find(doc => doc.id === definition.document_id);
    // 非首次癌症申請仍可能依病況要求病理文件，不能由單一條件免附。
    const safelyNotApplicable = applicability === false && !rule.review_required;
    const status = safelyNotApplicable ? 'not_applicable' : old?.status === 'not_applicable' ? 'not_started' : old?.status ?? 'not_started';
    const references = [...new Set([rule.source_id, ...(rule.additional_source_ids ?? [])])].map(id => sourceFor(registry, id, id === rule.source_id ? rule.page_number : null));
    return {
      id: definition.document_id,
      title: definition.title,
      description: definition.description,
      requirement_type: rule.requirement_type,
      condition: copy(rule.condition),
      applicability,
      requirement_explanation: rule.explanation,
      review_required: Boolean(rule.review_required || applicability === null),
      source_id: rule.source_id,
      official_url: source.official_url,
      download_url: download?.official_url ?? null,
      example_url: example?.official_url ?? null,
      source_references: references,
      status,
      analysis: old?.analysis ?? null,
      confirmed_findings: old?.confirmed_findings ?? [],
      file: old?.file ?? null,
    };
  });
}

function inferDescription(messages) {
  let care = null, critical = 'unknown', noAdmission = false, described = false, topic = null, emergency = false;
  let cause = 'unknown', surgery = 'unknown';
  // Update only the facts actually mentioned in each turn. Old uncertainty must
  // not override a later answer, and absence of admission never proves a visit.
  const statusFor = (text, terms) => {
    if (!new RegExp(terms).test(text)) return null;
    if (/不知道|不確定|不清楚|不一定|有沒有|是否|是不是|會不會|嗎|可能|疑似|擔心|擔憂|害怕|很怕|怕是|未確診|沒(?:有)?確診|(?:不能|無法)確診/.test(text)) return 'unknown';
    const negative = `(?:沒有|尚未|還沒|未曾|不是|不曾|不需要|不需|不用|未|沒|無|非)(?:去|到|接受|安排|需要|做|進行|實際|罹患|曾|過|是|再|任何|就)*(?:(?:住院|入院|門診|急診|看診|就醫)(?:或|和|及|以及|跟|、))*(?:${terms})`;
    if (new RegExp(negative).test(text)) return 'no';
    return /預計|打算|準備|將要|將去|要去|需要|應該|建議|明天|下週/.test(text) ? 'unknown' : 'yes';
  };
  for (const message of messages) {
    const currentVisit = [...message.matchAll(/這次|本次|此次/g)].at(-1);
    if (currentVisit) {
      care = null; critical = 'unknown'; noAdmission = false; described = false; topic = null; emergency = false;
      cause = 'unknown'; surgery = 'unknown';
    }
    const currentText = currentVisit ? message.slice(currentVisit.index + currentVisit[0].length) : message;
    for (const text of currentText.split(/[，,。；;！!\n]|但|可是|更正|後來/).filter(Boolean)) {
      if (/車禍|意外|摔倒|跌倒|疾病|生病|受傷|肺炎|感染|癌|重大疾病|住院|入院|門診|急診|看診|就醫|手術/.test(text)) described = true;
      if (/(?:尚未|還未|還沒(?:有)?|沒有|未曾|不曾|沒|未)(?:曾經|去)?(?:就醫|就診|看(?:過)?醫[生師])/.test(text)) {
        care = null; critical = 'unknown'; surgery = 'unknown'; emergency = false;
      }
      const accident = statusFor(text, '車禍|意外|摔倒|跌倒');
      const illness = statusFor(text, '疾病|生病|肺炎|感染|癌症|罹癌|腫瘤');
      if (accident) cause = accident === 'yes' ? 'accident' : 'unknown';
      if (illness) cause = illness === 'yes' ? 'illness' : 'unknown';
      const cancer = statusFor(text, '癌症|罹癌|重大疾病');
      const admission = statusFor(text, '住院|入院');
      let visit = statusFor(text, '門診|急診|看診');
      if (visit === 'yes' && statusFor(text, '急診') === 'yes' && statusFor(text, '門診|看診') !== 'yes'
        && !/(?:去過|到過|有去|已去|已經去|去|到|只有)\s*急診|急診\s*(?:就醫|看診)/.test(text)) visit = 'unknown';
      const operation = statusFor(text, '手術');
      if (cancer) { critical = cancer; topic = 'cancer'; }
      if (admission) {
        noAdmission = admission === 'no';
        if (admission === 'yes') care = 'inpatient';
        else if (admission === 'unknown' || care === 'inpatient') care = null;
        topic = 'care';
      }
      if (visit) {
        if (visit === 'yes') { care = 'outpatient'; emergency = statusFor(text, '急診') === 'yes'; }
        else if ((visit === 'unknown' && admission !== 'yes') || care === 'outpatient') care = null;
        topic = 'care';
      }
      if (admission === 'yes' && visit === 'yes' && text.search(/住院|入院/) > text.search(/門診|急診|看診/)) care = 'inpatient';
      if (!admission && !visit && /就醫/.test(text) && statusFor(text, '就醫') !== 'yes') {
        care = null;
        noAdmission = statusFor(text, '就醫') === 'no';
        topic = 'care';
      }
      if (operation) { surgery = operation; topic = 'surgery'; }
      if (!cancer && !admission && !visit && !operation && /不知道|不確定|不清楚|不一定/.test(text)) {
        if (topic === 'cancer') critical = 'unknown';
        else if (topic === 'surgery') surgery = 'unknown';
        else care = null;
      }
    }
  }
  const question = !described
    ? '您好，請描述這次發生的事情或就醫情況，我會依您提供的資訊協助確認文件準備方向。'
    : noAdmission
      ? '這次沒有住院，請問有到急診或門診就醫，還是尚未就醫？未住院不代表一定是門診。'
      : '這次是否已住院，或有到急診／門診就醫？若尚未就醫也請告訴我，我會依實際情況協助整理。';
  return { proposal: { claim_type_id: critical === 'yes' ? 'critical_illness' : care, conditions: { cause, surgery, receipt_type: 'unknown' } }, question, emergency, critical, noAdmission, described };
}

const QUESTIONS = {
  inpatient: ['這次是否有住院？', [['yes','有'],['no','沒有'],['unknown','不知道／稍後確認']]],
  outpatient: ['這次有到門診就醫嗎？若尚未就醫，也可以直接告訴我。', [['yes','有'],['no','沒有'],['unknown','不知道／稍後確認']]],
  emergency: ['這次有到急診就醫嗎？', [['yes','有'],['no','沒有'],['unknown','不知道／稍後確認']]],
  cause: ['這次就醫是因為疾病還是意外？', [['illness','疾病'],['accident','意外'],['unknown','不知道／稍後確認']]],
  surgery: ['這次是否有接受手術？', [['yes','有'],['no','沒有'],['unknown','不知道／稍後確認']]],
  receipt_type: ['本次要準備實支實付還是日額型的收據資料？', [['actual','實支實付'],['daily','日額型'],['unknown','不知道／稍後確認']]],
  payment_method: ['是否要以直接匯款方式領取？', [['remittance','直接匯款'],['other','其他方式'],['unknown','不知道／稍後確認']]],
};
function pendingQuestion(item, field) {
  const [prompt, options] = QUESTIONS[field];
  return { field, kind:'fact', asked_at_revision:item.revision, prompt, options:options.map(([value,label])=>({value,label})) };
}
function shortAnswer(message, field) {
  if (/^(?:不知道|不確定|稍後確認|待確認|unknown)(?:[，、／/\s]*(?:不知道|不確定|稍後確認|待確認))*[。！!]*$/.test(message)) return 'unknown';
  if (field==='cause') return /^(?:疾病|生病|illness)$/.test(message)?'illness':/^(?:意外|事故|accident)$/.test(message)?'accident':null;
  if (field==='receipt_type') return /^(?:實支實付|actual)$/.test(message)?'actual':/^(?:日額型?|daily)$/.test(message)?'daily':null;
  if (field==='payment_method') return /^(?:有|是|要|直接匯款|匯款|remittance)$/.test(message)?'remittance':/^(?:沒有|不是|不要|其他方式|other)$/.test(message)?'other':null;
  return /^(?:有|是|對|沒錯|yes)[。！!]*$/.test(message)?'yes':/^(?:沒有|沒|不是|否|no)[。！!]*$/.test(message)?'no':null;
}
function gatherDetails(previous, message) {
  const details=copy(previous||emptyDetails());
  for (const [word,value] of [['媽媽','parent'],['爸爸','parent'],['母親','parent'],['父親','parent'],['配偶','spouse'],['先生','spouse'],['太太','spouse'],['孩子','child'],['小孩','child'],['本人','self']]) if(message.includes(word)) details.insured_relation=value;
  for(const code of message.match(/\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g)||[]) if(!details.policy_products.some(p=>p.code===code)) details.policy_products.push({code,version:null,verification_status:'unverified'});
  const diagnosis=message.match(/(?:診斷(?:為|是|名稱[：:])|確診為)[「『]?([^，,。；;」』]{1,40})/);if(diagnosis)details.diagnosis_name=diagnosis[1].trim();
  const surgery=message.match(/(?:手術名稱[：:]|接受|做了)[「『]?([^，,。；;」』]{1,40}手術)/);if(surgery)details.surgery_name=surgery[1].trim();
  const date=message.match(/(?:20\d{2}[年/-])?\d{1,2}[月/-]\d{1,2}日?/g)||[];
  if(date.length&&/住院|入院/.test(message))details.visit_dates.admission=date[0];
  if(date.length&&/出院/.test(message))details.visit_dates.discharge=date.at(-1);
  if(/尚未出院|還沒出院/.test(message))details.visit_dates.discharge_pending=true;
  return details;
}
function workflowResponse(registry,item,message,base) {
  const state=item.dialogue_state, pending=state.pending_question;
  const confirmedFacts=copy(state.facts);
  if(pending?.kind==='proposal'&&state.active_proposal&&/^(?:有|是|對|沒錯|yes)[。！!]*$/.test(message)){
    const active=state.active_proposal,proposal={id:active.id,base_revision:active.base_revision,changes:copy(active.changes)};
    return {...base,response_type:'clarification',message:'已保留這份修改提案，請點「確認更新」或「取消變更」。',proposal,pending_question:pending,proposed_case_updates:copy(active.updates)};
  }
  if(pending?.kind==='proposal'&&/^(?:不是|否|不對|取消|不要|no)[。！!]*$/.test(message)){
    state.pending_question=null;state.active_proposal=null;state.details=copy(item.details);
    return {...base,response_type:'clarification',message:'請告訴我哪一部分不符，或直接更正需要調整的資訊。'};
  }
  if(/(?:本次|這次|此次)/.test(message)&&(!item.claim_type_id||/車禍|意外|疾病|只有門診|就醫方式/.test(message))){state.facts=emptyFacts();state.conditions={};state.deferred_fields=[];state.details=copy(item.details);}
  if(/(?:沒有|尚未|還沒|未曾|不曾)(?:去)?(?:就醫|看診)/.test(message)){for(const field of ['inpatient','outpatient','emergency','critical_diagnosis','surgery'])state.facts[field]='unknown';}
  const previous=item.messages.filter(entry=>entry.role==='user').map(entry=>entry.content);
  let expanded=message;
  const answered=pending?.kind==='fact'?shortAnswer(message,pending.field):null;
  if(answered!==null){
    if(answered==='unknown'){if(!state.deferred_fields.includes(pending.field))state.deferred_fields.push(pending.field)}
    else state.deferred_fields=state.deferred_fields.filter(field=>field!==pending.field);
    const phrases={inpatient:{yes:'有住院',no:'沒有住院'},outpatient:{yes:'有到門診就醫',no:'沒有到門診'},emergency:{yes:'有去急診',no:'沒有去急診'},cause:{illness:'因為疾病',accident:'因為意外'},surgery:{yes:'有接受手術',no:'沒有手術'}};
    expanded=phrases[pending.field]?.[answered]||message;
  }
  const inferred=inferDescription([...previous,expanded]);
  const current=inferDescription([expanded]);
  const anchors={cause:/車禍|意外|疾病|生病|肺炎|感染/,inpatient:/住院|入院/,outpatient:/門診|看診/,emergency:/急診/,critical_diagnosis:/癌症|罹癌|重大疾病/,surgery:/手術|開刀/};
  for(const [field,anchor] of Object.entries(anchors)){
    if(!anchor.test(expanded))continue;
    let value=field==='cause'?current.proposal.conditions.cause:field==='surgery'?current.proposal.conditions.surgery:field==='critical_diagnosis'?current.critical:field==='inpatient'?current.proposal.claim_type_id==='inpatient'?'yes':current.noAdmission?'no':'unknown':field==='emergency'?current.emergency?'yes':/沒有.*急診/.test(expanded)?'no':'unknown':current.proposal.claim_type_id==='outpatient'&&!current.emergency?'yes':/沒有.*門診/.test(expanded)?'no':'unknown';
    state.facts[field]=value;
  }
  if(answered!==null&&Object.hasOwn(state.facts,pending.field))state.facts[pending.field]=answered;
  const draftConditions={...item.conditions,...(state.conditions||{})};
  for(const field of ['cause','surgery'])if(state.facts[field]!=='unknown'||anchors[field].test(expanded)||answered!==null&&pending.field===field)draftConditions[field]=state.facts[field];
  if(!item.claim_type_id){Object.assign(draftConditions,inferred.proposal.conditions);for(const field of ['cause','surgery'])draftConditions[field]=state.facts[field];}
  if(answered!==null&&['receipt_type','payment_method'].includes(pending.field))state.conditions={...(state.conditions||{}),[pending.field]:answered};
  if(answered!==null&&['receipt_type','payment_method'].includes(pending.field))draftConditions[pending.field]=answered;
  const details=gatherDetails(state.details||item.details,message);state.details=details;
  const candidate=state.facts.critical_diagnosis==='yes'?'critical_illness':state.facts.inpatient==='yes'?'inpatient':state.facts.outpatient==='yes'||state.facts.emergency==='yes'?'outpatient':null;
  const isChange=item.claim_type_id&&(/更正|本次|這次|改成|後來|有手術|沒有手術|住院.*天|沒有住院|只有門診/.test(message)||answered!==null||details.policy_products.length>item.details.policy_products.length);
  if(item.claim_type_id&&!isChange)return null;
  const skip=state.deferred_fields;
  let next=null;
  if(!candidate){
    if(!inferred.described&&!answered){state.pending_question=null;return {...base,response_type:'clarification',message:'您好，請描述這次發生的事情或就醫情況。',missing_information:['describe_event']};}
    next=['inpatient','outpatient','emergency'].find(field=>state.facts[field]==='unknown'&&!skip.includes(field));
  }else if(!item.claim_type_id)next=['cause','surgery','payment_method'].find(field=>draftConditions[field]==='unknown'&&!skip.includes(field));
  if(next){const question=pendingQuestion(item,next);state.pending_question=question;return {...base,response_type:'clarification',message:question.prompt,pending_question:question,missing_information:[next]};}
  if(!candidate){state.pending_question=null;return {...base,response_type:'clarification',message:'目前就醫情況仍待確認，可補充資訊後再整理準備方向。',missing_information:['care_setting']};}
  const updates={claim_type_id:candidate||item.claim_type_id,conditions:draftConditions,details:{...details,deferred_fields:[...skip]}};
  const changes=[];
  if(updates.claim_type_id!==item.claim_type_id)changes.push({field:'claim_type_id',before:item.claim_type_id,after:updates.claim_type_id});
  for(const [field,after] of Object.entries(draftConditions))if(after!==item.conditions[field])changes.push({field:`conditions.${field}`,before:item.conditions[field],after});
  if(JSON.stringify(updates.details)!==JSON.stringify(item.details))changes.push({field:'details',before:item.details,after:updates.details});
  const type=registry.claim_types.find(t=>t.claim_type_id===updates.claim_type_id);
  if(item.claim_type_id&&!changes.length){state.pending_question=null;return {...base,message:'目前案件資訊沒有變更；可繼續準備文件。'};}
  const proposal={id:identifier(),base_revision:item.revision,changes};
  if(item.claim_type_id){state.active_proposal={...proposal,updates:copy(updates),facts:copy(state.facts)};state.facts=confirmedFacts;}
  const question={field:'confirm_claim',kind:'proposal',asked_at_revision:item.revision,prompt:'請核對後確認變更。',options:[]};state.pending_question=question;
  return {...base,response_type:'claim_suggestion',message:item.claim_type_id?'已整理這次更正，請核對差異後確認，清單才會更新。':`可以先檢視「${type.label}」的文件準備方向。${inferred.emergency?'急診是否適用仍須依個別保單並向官方確認。':''}請核對類型與資訊後建立清單。`,suggested_claim_types:[{id:type.claim_type_id,title:type.label,description:'文件準備方向仍須依保單與官方確認。'}],missing_information:[...skip],proposed_case_updates:updates,proposal,pending_question:question};
}

function answerMessage(registry, item, message, documentId) {
  const refs = [sourceFor(registry, 'cardif-claims')];
  const base = { response_type: 'answer', message: '', suggested_claim_types: [], missing_information: [], source_references: refs, proposed_case_updates: {}, requires_human_review: true, provider: 'mock', is_simulated: true };
  if (/多少錢|給付金額|獲賠|賠多少|保證|核准|資格|一定.*賠/.test(message)) {
    return { ...base, response_type: 'uncertain', message: '目前無法確認個別保單的理賠資格或給付金額，也不能核准理賠。請查閱保單條款或聯繫官方客服 0800-012-899；此助手僅協助文件準備。' };
  }
  const workflow=workflowResponse(registry,item,message,base);
  if(workflow)return workflow;
  if (!item.claim_type_id) {
    const { proposal, question, emergency } = inferDescription([...item.messages.filter(entry => entry.role === 'user').map(entry => entry.content), message]);
    if (!proposal.claim_type_id) {
      return { ...base, response_type: 'clarification', message: question, missing_information: ['care_setting'] };
    }
    const type = registry.claim_types.find(entry => entry.claim_type_id === proposal.claim_type_id);
    return {
      ...base,
      response_type: 'claim_suggestion',
      message: `依您描述的就醫情形，可以先檢視「${type.label}」的文件資訊。${proposal.claim_type_id === 'outpatient' && emergency ? '急診是否適用仍須依個別保單並向官方確認。' : ''}這只是準備方向，請確認類別與條件後再建立清單，給付仍須依保單與官方審核。`,
      suggested_claim_types: [{ id: type.claim_type_id, title: type.label, description: '請以實際就醫資料、保單與官方審核確認適用性。' }],
      missing_information: Object.entries(proposal.conditions).filter(([, value]) => value === 'unknown').map(([field]) => field),
      proposed_case_updates: proposal,
    };
  }
  const selected = documentId ? item.documents.find(doc => doc.id === documentId) : null;
  if (documentId && !selected) fail('DOCUMENT_NOT_FOUND', '找不到這份案件文件。', 404);
  if (selected) {
    return { ...base, message: `${selected.title}：${selected.description} ${selected.requirement_explanation} ${selected.review_required ? '適用條件仍需向官方確認。' : ''} 文件初步檢查不等於正式核准。`, source_references: selected.source_references };
  }
  const knowledge = registry.knowledge.find(entry => /簽名|填寫|申請書/.test(message) ? entry.knowledge_id === 'application-precheck' : /手術/.test(message) ? entry.knowledge_id === 'surgery-condition' : /診斷/.test(message) ? entry.knowledge_id === 'diagnosis-format' : entry.knowledge_id === 'scope');
  return { ...base, message: `${knowledge?.text ?? '目前沒有足夠官方資料確認此項問題，請聯繫官方客服。'} 您可以點選清單中的文件，我會依其官方來源說明準備方式。`, source_references: knowledge ? [sourceFor(registry, knowledge.source_id, knowledge.page_number)] : refs };
}

async function validateFile(file) {
  if (!file || typeof file.arrayBuffer !== 'function') fail('INVALID_FILE', '請選擇 PDF、JPG 或 PNG 檔案。');
  if (!file.size) fail('EMPTY_FILE', '檔案內容為空，請重新選擇。');
  if (file.size > MAX_BYTES) fail('FILE_TOO_LARGE', '檔案不可超過 10 MB。', 413);
  const type = { 'application/pdf': 'pdf', 'image/jpeg': 'jpeg', 'image/png': 'png' }[file.type];
  const extension = file.name?.split('.').pop()?.toLowerCase();
  if (!type || !(type === 'jpeg' ? ['jpg', 'jpeg'] : [type]).includes(extension)) fail('UNSUPPORTED_FILE_TYPE', '僅支援 PDF、JPG、PNG，副檔名必須與格式一致。', 415);
  const header = new Uint8Array(await file.slice(0, 16).arrayBuffer());
  const signature = type === 'pdf' ? String.fromCharCode(...header.slice(0, 5)) === '%PDF-' : type === 'jpeg' ? header[0] === 255 && header[1] === 216 && header[2] === 255 : header.slice(0, 8).join(',') === '137,80,78,71,13,10,26,10';
  if (!signature) fail('INVALID_FILE', '檔案內容與宣告格式不符，請選擇有效文件。');
}

function mockAnalysis(documentId, scenario) {
  const complete = scenario === 'complete';
  const blurred = scenario === 'blurred';
  const confidence = blurred ? 0.34 : complete ? 0.96 : 0.87;
  const boxes = complete ? [] : blurred ? [{ page_number: 1, x: 0.1, y: 0.16, width: 0.8, height: 0.66 }] : [{ page_number: 1, x: 0.12, y: 0.72, width: 0.36, height: 0.08 }, { page_number: 1, x: 0.56, y: 0.72, width: 0.28, height: 0.08 }];
  const findings = boxes.map((box, index) => ({
    id: `${documentId}-${blurred ? 'quality' : index === 0 ? 'signature' : 'date'}`,
    field: blurred ? 'document_quality' : index === 0 ? 'signature' : 'signed_date',
    field_name: blurred ? '文件清晰度' : index === 0 ? '申請人簽名' : '簽署日期',
    severity: 'warning',
    message: blurred ? '模擬低清晰度：無法可靠辨識指定欄位。' : index === 0 ? '模擬結果：簽名區域疑似空白，請人工確認。' : '模擬結果：簽署日期疑似缺漏，請確認文件內容。',
    suggestion: blurred ? '請重新掃描或拍攝，確保光線均勻且文字清楚。' : '請對照原始文件與官方填寫範例確認；需要時補填後重新上傳。',
    confidence, page_number: 1, bounding_box: box, source_id: 'cardif-application', requires_human_review: true,
  }));
  return {
    analysis_id: identifier(), document_id: documentId,
    analysis_status: blurred ? 'uncertain' : 'completed',
    provider: 'mock', is_simulated: true, scenario,
    extracted_fields: complete ? [{ field: 'synthetic_demo', value: '合成展示文件的指定欄位可辨識', confidence, page_number: 1 }] : [],
    findings, confidence, page_number: 1, bounding_boxes: boxes,
    requires_human_review: !complete,
    disclaimer: '這是預設的模擬 OCR 情境，沒有辨識實際檔案內容。初步檢查不代表正式審核或核准。',
  };
}

export class MockClaimService {
  constructor({ delay = 180, storage = browserStorage(), registry = officialRegistry } = {}) {
    this.mode = 'mock';
    this.delay = Math.max(0, delay);
    this.storage = storage;
    this.registry = copy(registry);
    this.cases = {};
    this.failure = null;
    try {
      const saved = JSON.parse(storage?.getItem(STORAGE_KEY) ?? '{}');
      if (saved && typeof saved === 'object' && !Array.isArray(saved)) this.cases = saved;
    } catch { this.cases = {}; }
  }

  simulateFailure(code = 'SIMULATED_FAILURE', message = '模擬服務暫時無法使用，請重試。') {
    this.failure = new ServiceError(code, message, 503);
  }

  async ready() {
    if (this.delay) await new Promise(resolve => setTimeout(resolve, this.delay));
    if (this.failure) { const error = this.failure; this.failure = null; throw error; }
  }

  caseById(id) {
    const item = Object.hasOwn(this.cases, id) ? this.cases[id] : null;
    if (!item) fail('CASE_NOT_FOUND', '找不到此展示案件，請重新開始。', 404);
    item.revision??=0;
    const defaults=emptyDetails();
    item.details={...defaults,...item.details,visit_dates:{...defaults.visit_dates,...item.details?.visit_dates}};
    const state=item.dialogue_state||{},details=state.details||item.details;
    item.dialogue_state={...state,facts:{...emptyFacts(),...state.facts},conditions:{...item.conditions,...state.conditions},details:{...emptyDetails(),...details,visit_dates:{...defaults.visit_dates,...details.visit_dates}},pending_question:state.pending_question??null,deferred_fields:state.deferred_fields??[],active_proposal:state.active_proposal??null};
    return item;
  }

  save(item,{incrementRevision=true}={}) {
    if(incrementRevision)item.revision=(item.revision||0)+1;
    const state=item.dialogue_state,active=state?.active_proposal;
    if(active&&active.base_revision!==item.revision){
      if(active.facts)state.facts=copy(active.facts);
      state.active_proposal=null;
      if(state.pending_question?.kind==='proposal')state.pending_question={field:'correction',kind:'fact',asked_at_revision:item.revision,prompt:'案件或文件已變更，先前提案已失效。請重新描述要調整的項目。',options:[]};
    }
    item.updated_at = now();
    this.cases[item.id] = item;
    try { this.storage?.setItem(STORAGE_KEY, JSON.stringify(this.cases)); }
    catch { fail('STORAGE_UNAVAILABLE', '瀏覽器無法保存展示進度，請清理儲存空間後重試。', 503); }
    return copy(item);
  }

  async health() { await this.ready(); return { status: 'ok', service_mode: 'mock', llm_provider: 'mock', ocr_provider: 'mock' }; }

  async getClaimTypes() {
    await this.ready();
    return this.registry.claim_types.map(type => ({ id: type.claim_type_id, title: type.label, description: ({ inpatient: '住院醫療相關文件準備，仍須依保單確認適用項目。', outpatient: '醫療門診相關文件準備，請確認就醫與收據資料。', critical_illness: '防癌或重大疾病相關文件準備，疾病定義及給付須依保單確認。' })[type.claim_type_id] }));
  }

  async getLibrary({query='',category='all'}={}) {
    await this.ready();
    const officialLibrary=await loadOfficialLibrary();
    query=String(query||'').trim().slice(0,200);category=String(category||'all').trim().slice(0,80);
    const terms=query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const documents=officialLibrary.documents.filter(doc=>(category==='all'||doc.category_id===category)&&terms.every(term=>['title','category_label','product_code','asset_code','version','product_name','keywords'].map(key=>String(doc[key]||'')).join(' ').toLocaleLowerCase().includes(term)));
    const categories=officialLibrary.categories.map(item=>({...item,document_count:officialLibrary.documents.filter(doc=>doc.category_id===item.id).length}));
    return copy({schema_version:officialLibrary.schema_version,checked_at:officialLibrary.checked_at,scope_note:officialLibrary.scope_note,categories,documents,total:documents.length,query,category});
  }

  async getFaq() {
    await this.ready();
    const officialLibrary=await loadOfficialLibrary();
    return copy(officialLibrary.faq.map(item=>({...item,sources:item.source_ids.map(id=>officialLibrary.documents.find(doc=>doc.id===id))})));
  }

  async getProduct(code) {
    await this.ready();
    const officialLibrary=await loadOfficialLibrary();
    const requested=String(code||'').trim().slice(0,120),normalized=requested.toUpperCase();
    const product=officialLibrary.product_lookups.find(item=>item.code.toUpperCase()===normalized);
    return copy({requested_code:requested,normalized_code:normalized,verification_status:product?.verification_status||'unverified',product_name:product?.product_name||null,versions:(product?.version_ids||[]).map(id=>officialLibrary.documents.find(doc=>doc.id===id)),candidate_sources:(product?.candidate_source_ids||[]).map(id=>officialLibrary.documents.find(doc=>doc.id===id)),preparation_supported:false,scope_note:product?.scope_note||'尚無可核對此完整商品代碼與版本的官方資料，請確認保單面頁並洽官方客服；不可據此判定保障、資格或金額。',checked_at:officialLibrary.checked_at});
  }

  async createCase({ entry_path, claim_type_id = null, conditions = {}, details = {} } = {}) {
    await this.ready();
    if (!['guided', 'direct'].includes(entry_path)) fail('VALIDATION_ERROR', '請選擇有效的案件入口。');
    this.validateClaimType(claim_type_id);
    const item = { id: identifier(), entry_path, claim_type_id, revision:0, details:{...emptyDetails(),...copy(details)}, dialogue_state:{facts:emptyFacts(),conditions:{},details:emptyDetails(),pending_question:null,deferred_fields:[],active_proposal:null}, conditions: { ...DEFAULT_CONDITIONS, ...validateConditions(conditions) }, documents: [], messages: [], created_at: now(), updated_at: now() };
    item.dialogue_state.details=copy(item.details);
    for(const field of ['cause','surgery'])item.dialogue_state.facts[field]=item.conditions[field];
    if(claim_type_id)item.dialogue_state.facts[({inpatient:'inpatient',outpatient:'outpatient',critical_illness:'critical_diagnosis'})[claim_type_id]]='yes';
    item.documents = buildChecklist(this.registry, item);
    return this.save(item,{incrementRevision:false});
  }

  validateClaimType(id) {
    if (id !== null && !this.registry.claim_types.some(type => type.claim_type_id === id)) fail('VALIDATION_ERROR', '此理賠類別尚未支援，請選擇清單中的項目。');
  }

  async getCase(id) { await this.ready(); return copy(this.caseById(id)); }

  async updateCase(id, updates = {}) {
    await this.ready();
    const item = copy(this.caseById(id));
    const acceptingProposal=updates.proposal_action==='accept';
    if (Object.keys(updates).some(field => !['claim_type_id', 'conditions','details','expected_revision','proposal_id','proposal_action'].includes(field))) fail('VALIDATION_ERROR', '案件更新包含未支援的欄位。');
    if('expected_revision' in updates&&updates.expected_revision!==item.revision)fail('CASE_REVISION_CONFLICT','案件已更新，請重新核對本次修改。',409);
    if(updates.proposal_action){
      const active=item.dialogue_state.active_proposal;
      const response=active?{proposal:active,proposed_case_updates:active.updates}:[...item.messages].reverse().find(message=>message.role==='assistant')?.response;
      if(!['accept','reject'].includes(updates.proposal_action)||!response?.proposal||response.proposal.id!==updates.proposal_id||response.proposal.base_revision!==item.revision||item.dialogue_state.pending_question?.kind!=='proposal')fail('STALE_PROPOSAL','這份修改提案已失效，請重新整理。',409);
      if(updates.expected_revision===undefined)fail('VALIDATION_ERROR','確認提案需提供案件版本。');
      if(updates.proposal_action==='reject'){item.dialogue_state.pending_question=null;item.dialogue_state.active_proposal=null;item.dialogue_state.details=copy(item.details);return this.save(item);}
      if(item.dialogue_state.active_proposal?.facts)item.dialogue_state.facts=item.dialogue_state.active_proposal.facts;
      item.dialogue_state.active_proposal=null;
      updates={...response.proposed_case_updates};
    }
    if ('claim_type_id' in updates) { this.validateClaimType(updates.claim_type_id); if(updates.claim_type_id!==item.claim_type_id&&!acceptingProposal){for(const field of ['inpatient','outpatient','emergency','critical_diagnosis'])item.dialogue_state.facts[field]='unknown';if(updates.claim_type_id)item.dialogue_state.facts[({inpatient:'inpatient',outpatient:'outpatient',critical_illness:'critical_diagnosis'})[updates.claim_type_id]]='yes';}item.claim_type_id = updates.claim_type_id; }
    if ('conditions' in updates) item.conditions = { ...item.conditions, ...validateConditions(updates.conditions) };
    if('details' in updates)item.details={...item.details,...copy(updates.details)};
    item.dialogue_state.details=copy(item.details);item.dialogue_state.conditions=copy(item.conditions);item.dialogue_state.active_proposal=null;
    item.dialogue_state.pending_question=null;item.dialogue_state.deferred_fields=[...(item.details.deferred_fields||[])];
    for(const field of ['cause','surgery'])item.dialogue_state.facts[field]=item.conditions[field];
    item.documents = buildChecklist(this.registry, item, item.documents);
    return this.save(item);
  }

  async sendMessage(id, message, { document_id } = {}) {
    await this.ready();
    if (typeof message !== 'string' || !message.trim() || message.length > 4000) fail('VALIDATION_ERROR', '請輸入 1 至 4000 字的問題。');
    const item = copy(this.caseById(id));
    const previousProposal=copy(item.dialogue_state.active_proposal??null);
    const response = answerMessage(this.registry, item, message.trim(), document_id);
    const state=item.dialogue_state,nextRevision=item.revision+1;
    if(state.pending_question){state.pending_question.asked_at_revision=nextRevision;response.pending_question=copy(state.pending_question);}
    let updates=response.proposed_case_updates||{};
    if(!Object.keys(updates).length&&previousProposal?.base_revision===item.revision&&state.pending_question?.kind==='proposal'){
      updates=copy(previousProposal.updates);response.proposed_case_updates=updates;
    }
    if(Object.keys(updates).length){
      const draft=state.active_proposal||previousProposal;
      const proposal={id:identifier(),base_revision:nextRevision,changes:copy(response.proposal?.changes||draft?.changes||[])};
      state.active_proposal={...proposal,updates:copy(updates),facts:copy(draft?.facts||state.facts)};
      response.proposal=proposal;
      if(item.claim_type_id)response.response_type='case_update_proposal';
    }else state.active_proposal=null;
    item.messages.push({ id: identifier(), role: 'user', content: message.trim(), created_at: now() }, { id: identifier(), role: 'assistant', content: response.message, response, created_at: now() });
    return { case: this.save(item), response: copy(response) };
  }

  async getChecklist(id) { await this.ready(); return copy(this.caseById(id).documents); }

  async updateDocument(id, documentId, updates = {}) {
    await this.ready();
    const item = copy(this.caseById(id));
    const doc = item.documents.find(entry => entry.id === documentId);
    if (!doc) fail('DOCUMENT_NOT_FOUND', '找不到這份案件文件。', 404);
    if (Object.keys(updates).some(field => !['status', 'confirmed_findings','analysis_id'].includes(field))) fail('VALIDATION_ERROR', '文件更新包含未支援的欄位。');
    if('confirmed_findings' in updates||updates.status==='manual_ready'){
      if(!doc.analysis)fail('ANALYSIS_REQUIRED','請先分析並人工核對這份文件。');
      if(updates.analysis_id!==doc.analysis.analysis_id)fail('STALE_ANALYSIS','分析結果已更新，請重新核對。',409);
    }
    if ('confirmed_findings' in updates) {
      if (!Array.isArray(updates.confirmed_findings) || updates.confirmed_findings.some(id => !doc.analysis?.findings.some(finding => finding.id === id))) fail('INVALID_FINDING', '只能確認本次分析中存在的待確認項目。');
      doc.confirmed_findings = [...new Set(updates.confirmed_findings)];
    }
    if ('status' in updates) {
      if (!['not_started', 'uploaded', 'not_applicable','manual_ready'].includes(updates.status)) fail('INVALID_DOCUMENT_STATUS', '分析狀態由文件檢查產生，不能直接手動標記通過。');
      if(updates.status==='manual_ready'&&doc.analysis.findings.some(f=>!doc.confirmed_findings.includes(f.id)))fail('FINDINGS_NOT_CONFIRMED','請先核對全部提醒，再標記人工備妥。');
      if (updates.status === 'not_applicable' && doc.requirement_type === 'required') fail('REQUIRED_DOCUMENT', '必要文件不能標為不適用，請向官方確認。');
      doc.status = updates.status === 'uploaded' && doc.analysis?.findings.length ? 'needs_attention' : updates.status;
      if (updates.status === 'not_started') { doc.analysis = null; doc.confirmed_findings = []; doc.file = null; }
    }
    return this.save(item);
  }

  async analyzeDocument(id, documentId, file, { scenario = 'missing' } = {}) {
    await this.ready();
    if (!['missing', 'complete', 'blurred'].includes(scenario)) fail('VALIDATION_ERROR', '模擬分析情境不正確。');
    const item = copy(this.caseById(id));
    const doc = item.documents.find(entry => entry.id === documentId);
    if (!doc) fail('DOCUMENT_NOT_FOUND', '找不到這份案件文件。', 404);
    if (doc.status === 'not_applicable') fail('DOCUMENT_NOT_APPLICABLE', '此文件目前不適用，請先重新確認案件條件。');
    await validateFile(file);
    const digest=await globalThis.crypto.subtle.digest('SHA-256',await file.arrayBuffer());
    doc.file = { name: file.name.slice(0, 255), type: file.type, size: file.size, sha256:Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('') };
    doc.analysis = mockAnalysis(documentId, scenario);
    doc.status = scenario === 'complete' ? 'precheck_passed' : 'needs_attention';
    doc.confirmed_findings = [];
    return this.save(item);
  }

  async getSource(id) {
    await this.ready();
    return copy({ ...sourceFor(this.registry, id), ...(id === 'cardif-claims' ? { submission: this.registry.submission } : {}) });
  }

  async deleteCase(id) {
    await this.ready();
    this.caseById(id);
    delete this.cases[id];
    try { this.storage?.setItem(STORAGE_KEY, JSON.stringify(this.cases)); }
    catch { fail('STORAGE_UNAVAILABLE', '無法更新瀏覽器展示進度，請重試。', 503); }
    return { deleted: true, id };
  }
}
