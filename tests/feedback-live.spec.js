import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { waitForUIMessageJob } from './message-job-helpers.js';

// 即使換 config 執行此檔，也必須明確授權真實請求。
if (process.env.LIVE_OPENROUTER !== '1' || !process.env.CLAIM_API_BASE_URL) {
  throw new Error('此測試需要 LIVE_OPENROUTER=1 與 CLAIM_API_BASE_URL。');
}
const target = new URL(process.env.CLAIM_API_BASE_URL);
if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password
    || target.pathname !== '/' || target.search || target.hash) {
  throw new Error('CLAIM_API_BASE_URL 必須為無帳密或其他部分的 HTTP(S) 根網址。');
}
process.env.PLAYWRIGHT_NO_COPY_PROMPT = '1';
test.use({ baseURL: target.origin, trace: 'off', screenshot: 'off', video: 'off' });
const headers = { Origin: target.origin };
const registry = JSON.parse(await readFile(resolve('data/official-sources.json'), 'utf8'));
const sources = new Map(registry.sources.map((source) => [source.source_id, source]));
const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const casePath = /^\/api\/v1\/cases\/[^/]+$/;
const messagePath = /^\/api\/v1\/cases\/[^/]+\/message-jobs$/;
const MAX_MESSAGES_PER_VIEWPORT = 8;

class AcceptanceFailure extends Error {
  constructor(code) { super(code); this.name = 'AcceptanceFailure'; }
}
// 原始模型回覆、案件及 DOM 文字只在記憶體內比較，失敗只輸出固定檢查碼。
function verify(condition, code) {
  if (!condition) throw new AcceptanceFailure(code);
}
const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);
const prepared = (item) => ({
  claim_type_id: item.claim_type_id,
  conditions: item.conditions,
  details: item.details,
  documents: item.documents,
});
const responseIs = (response, path, method) => new URL(response.url()).pathname === path
  && response.request().method() === method;

async function visible(locator, code) {
  try {
    await expect.poll(() => locator.isVisible(), { message: code }).toBe(true);
  } catch { throw new AcceptanceFailure(code); }
}

async function getCase(page, id) {
  const response = await page.request.get(`/api/v1/cases/${id}`);
  verify(response.status() === 200, 'CASE_GET_200');
  return response.json();
}

async function health(page, verified = false) {
  const response = await page.request.get('/api/v1/health');
  verify(response.status() === 200, 'HEALTH_HTTP_200');
  const item = await response.json();
  verify(item.status === 'ok' && item.service_mode === 'api', 'HEALTH_REAL_API');
  verify(item.llm_provider === 'openai_compatible' && item.llm_configured === true,
    'HEALTH_CONFIGURED_REAL_PROVIDER');
  verify(typeof item.llm_verified === 'boolean' && (!verified || item.llm_verified === true),
    'HEALTH_CURRENT_PROCESS_VERIFIED');
}

function realModel(answer) {
  verify(answer.provider === 'openai_compatible' && answer.is_simulated === false,
    'RESPONSE_REAL_MODEL');
  verify(answer.requires_human_review === true, 'RESPONSE_REQUIRES_HUMAN_REVIEW');
}

function officialReferences(references) {
  verify(Array.isArray(references) && references.length > 0, 'REFERENCES_REQUIRED');
  const unique = new Set();
  for (const reference of references) {
    const canonical = sources.get(reference.source_id);
    verify(Boolean(canonical) && reference.verification_status === 'verified', 'REFERENCES_VERIFIED_ID');
    verify(reference.official_url === canonical.official_url, 'REFERENCES_CANONICAL_URL');
    const url = new URL(reference.official_url);
    verify(url.protocol === 'https:' && url.hostname === 'life.cardif.com.tw'
      && !url.username && !url.password && !url.hash && (!url.port || url.port === '443'),
    'REFERENCES_OFFICIAL_HOST');
    verify(reference.page_number === null || (Number.isInteger(reference.page_number)
      && reference.page_number >= 1 && reference.page_number <= canonical.page_count),
    'REFERENCES_PAGE_BOUNDARY');
    const key = `${reference.source_id}:${reference.page_number}`;
    verify(!unique.has(key), 'REFERENCES_UNIQUE');
    unique.add(key);
  }
}

function officialChecklist(item) {
  const rules = registry.rules.filter((rule) => rule.claim_type_id === item.claim_type_id);
  verify(same(item.documents.map((document) => document.id).sort(),
    rules.map((rule) => rule.document_id).sort()), 'CHECKLIST_OFFICIAL_DOCUMENT_SET');
  for (const document of item.documents) {
    const rule = rules.find((entry) => entry.document_id === document.id);
    verify(document.requirement_type === rule.requirement_type && document.source_id === rule.source_id
      && same(document.condition, rule.condition), 'CHECKLIST_OFFICIAL_RULE');
    verify(document.official_url === sources.get(rule.source_id).official_url, 'CHECKLIST_OFFICIAL_URL');
    officialReferences(document.source_references);
  }
}

async function layout(page) {
  const valid = await page.evaluate(() => {
    const dialog = document.querySelector('dialog[open]');
    return document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1
      && (!dialog || dialog.scrollWidth <= dialog.clientWidth + 1);
  });
  verify(valid, 'RESPONSIVE_NO_HORIZONTAL_OVERFLOW');
}

async function startGuided(page) {
  await page.goto('/?service=api#triage');
  await page.getByRole('button', { name: '描述我的狀況', exact: true }).click();
  await visible(page.getByLabel('描述就醫情況', { exact: true }), 'GUIDED_INPUT_VISIBLE');
}

async function startDirect(page) {
  await page.goto('/?service=api#triage');
  await page.getByRole('button', { name: '選擇理賠類型', exact: true }).click();
  await page.getByRole('button', { name: '住院醫療', exact: true }).click();
  await page.getByLabel('事故原因', { exact: true }).selectOption('illness');
  await page.getByLabel('是否接受手術', { exact: true }).selectOption('no');
  await page.getByLabel('收據用途', { exact: true }).selectOption('actual');
  const created = page.waitForResponse((response) => responseIs(response, '/api/v1/cases', 'POST'));
  await page.getByRole('button', { name: '建立文件清單', exact: true }).click();
  const response = await created;
  verify(response.status() === 201, 'DIRECT_CASE_CREATED');
  const item = await response.json();
  verify(uuid4.test(item.id), 'DIRECT_CASE_UUID');
  page.__feedback.ids.add(item.id);
  await visible(page.getByRole('heading', { name: '文件準備工作區', exact: true }), 'DIRECT_WORKSPACE_VISIBLE');
  verify(item.conditions.cause === 'illness' && item.conditions.surgery === 'no', 'DIRECT_CONFIRMED_CONDITIONS');
  officialChecklist(item);
  return item;
}

async function ask(page, { id = null, message = null, quickValue = null, pending = null, workspace = false }) {
  verify(page.__feedback.messagePosts < MAX_MESSAGES_PER_VIEWPORT, 'MESSAGE_BUDGET_BEFORE_SEND');
  const beforeCount = page.__feedback.messagePosts;
  const answerPromise = waitForUIMessageJob(page, { caseId: id, context: '組員回饋對話驗收', timeout: 330_000 });
  // 先掛失敗處理，避免長等待於UI操作失敗後留下未處理拒絕。
  answerPromise.catch(() => {});
  if (quickValue !== null) {
    verify(pending?.kind === 'fact' && Array.isArray(pending.options), 'QUICK_ANSWER_BOUND_FACT');
    const option = pending.options.find((entry) => entry.value === quickValue);
    verify(Boolean(option), 'QUICK_ANSWER_CONTRACT_OPTION');
    const quick = page.locator('.quick-answers').getByRole('button', { name: option.label, exact: true });
    verify(await quick.getAttribute('data-field') === pending.field, 'QUICK_ANSWER_CURRENT_FIELD');
    await quick.click();
  } else {
    const label = workspace ? '詢問文件準備問題' : '描述就醫情況';
    await page.getByLabel(label, { exact: true }).fill(message);
    await page.getByRole('button', { name: workspace ? '送出問題' : '送出描述', exact: true }).click();
  }
  const result = await answerPromise;
  verify(uuid4.test(result.case.id) && (!id || result.case.id === id), 'MESSAGE_SAME_SYNTHETIC_CASE');
  page.__feedback.ids.add(result.case.id);
  verify(page.__feedback.messagePosts === beforeCount + 1, 'MESSAGE_EXACTLY_ONE_POST');
  const log = workspace ? page.getByRole('log', { name: '工作區對話', exact: true }) : page.locator('#guided-thread');
  const latest = log.locator('.bubble:not(.user)').last();
  await visible(latest, 'CURRENT_ASSISTANT_BUBBLE_VISIBLE');
  try {
    await expect.poll(async () => (await latest.locator(':scope > div').nth(1).textContent()) === result.response.message,
      { message: 'UI_SHOWS_CURRENT_VALIDATED_RESPONSE' }).toBe(true);
  } catch { throw new AcceptanceFailure('UI_SHOWS_CURRENT_VALIDATED_RESPONSE'); }
  await layout(page);
  return result;
}

function noGuidedMutation(result, patchCount) {
  verify(result.case.claim_type_id === null && result.case.documents.length === 0,
    'GUIDED_NO_CONFIRMED_TYPE_OR_CHECKLIST');
  verify(patchCount === 0, 'GUIDED_ZERO_PATCH_BEFORE_CONFIRMATION');
}

async function buildGuided(page, result) {
  realModel(result.response);
  verify(result.response.response_type === 'claim_suggestion', 'GUIDED_EXPLICIT_CANDIDATE');
  verify(same(result.response.suggested_claim_types.map((item) => item.id), ['inpatient']),
    'GUIDED_INPATIENT_CANDIDATE');
  officialReferences(result.response.source_references);
  const picker = page.locator('fieldset.guided-type-picker');
  const build = page.getByRole('button', { name: '建立文件清單', exact: true });
  await visible(picker, 'GUIDED_PICKER_VISIBLE');
  verify(await picker.locator('input[name="guided-claim-type"]:checked').count() === 0,
    'GUIDED_NO_PRESELECTED_CANDIDATE');
  verify(await build.isDisabled(), 'GUIDED_BUILD_DISABLED_UNTIL_SELECTION');
  const unchanged = prepared(await getCase(page, result.case.id));
  await picker.getByRole('radio', { name: '住院醫療', exact: true }).check();
  verify(await build.isEnabled(), 'GUIDED_BUILD_ENABLED_AFTER_INDEPENDENT_CHOICE');
  verify(same(prepared(await getCase(page, result.case.id)), unchanged), 'GUIDED_SELECTION_IS_LOCAL_ONLY');
  verify(page.__feedback.patches === 0, 'GUIDED_SELECTION_ZERO_PATCH');
  const saved = page.waitForResponse((response) => responseIs(response, `/api/v1/cases/${result.case.id}`, 'PATCH'));
  await build.click();
  const response = await saved;
  verify(response.status() === 200, 'GUIDED_CONFIRM_PATCH_200');
  const item = await response.json();
  verify(page.__feedback.patches === 1 && item.claim_type_id === 'inpatient', 'GUIDED_SINGLE_CONFIRMED_PATCH');
  verify(item.dialogue_state.facts.inpatient === result.case.dialogue_state.facts.inpatient,
    'GUIDED_ACCEPT_PRESERVES_VALIDATED_ADMISSION');
  await visible(page.getByRole('heading', { name: '文件準備工作區', exact: true }), 'GUIDED_WORKSPACE_VISIBLE');
  officialChecklist(item);
  return item;
}

async function openAssistant(page) {
  await page.getByRole('button', { name: '開啟助手', exact: true }).click();
  await visible(page.getByLabel('詢問文件準備問題', { exact: true }), 'WORKSPACE_ASSISTANT_VISIBLE');
}

async function recordedDetails(root, details) {
  if (details.insured_relation === 'parent') {
    const relation = root.locator('.case-detail-list > div').filter({ has: root.page().locator('dt', { hasText: /^關係$/ }) });
    verify((await relation.locator('dd').textContent()).trim() === '父母', 'UI_RECORDED_PARENT_RELATION');
  }
  const fields = [
    ['手術名稱', details.surgery_name], ['手術日期', details.surgery_date],
    ['入院日期', details.visit_dates?.admission],
    ['出院日期', details.visit_dates?.discharge_pending ? '尚未出院／待確認' : details.visit_dates?.discharge],
  ];
  for (const [label, value] of fields.filter(([, value]) => value)) {
    const row = root.locator('.case-detail-list > div').filter({ has: root.page().locator('dt').filter({ hasText: new RegExp(`^${label}$`) }) });
    verify((await row.locator('dd').textContent()).trim() === value, 'UI_RECORDED_ORIGINAL_MEDICAL_DETAILS');
  }
  const products = details.policy_products || [];
  verify(await root.locator('.product-record').count() === products.length, 'UI_RECORDED_PRODUCT_COUNT');
  for (const product of products) {
    const row = root.locator('.product-record').filter({ has: root.page().getByText(product.code, { exact: true }) });
    verify(await row.count() === 1 && (await row.textContent()).includes('使用者提供／待查證'),
      'UI_RECORDED_UNVERIFIED_PRODUCT');
  }
}

async function workspaceConfirmedState(page, item) {
  const meta = await page.locator('.case-meta').textContent();
  const cause = { illness: '疾病', accident: '意外', unknown: '待確認' }[item.conditions.cause];
  const surgery = { yes: '有', no: '無', unknown: '待確認' }[item.conditions.surgery];
  verify(meta.includes(`事故原因：${cause}`) && meta.includes(`手術情況：${surgery}`),
    'UI_WORKSPACE_CURRENT_CONFIRMED_CONDITIONS');
  const document = item.documents.find((entry) => entry.id === 'surgery');
  if (document) {
    const card = page.locator('article[data-document-id="surgery"]');
    const applicability = document.applicability === false ? '已確認不適用'
      : document.applicability === null ? '適用條件待確認' : '確認需要';
    verify((await card.locator('.applicability').textContent()).trim() === applicability,
      'UI_WORKSPACE_CURRENT_SURGERY_APPLICABILITY');
    const status = document.status === 'not_applicable' ? '已確認不適用' : document.status === 'not_started' ? '尚未準備' : null;
    if (status) verify((await card.locator('.document-axes > .badge').textContent()).includes(status),
      'UI_WORKSPACE_CURRENT_SURGERY_PREPARATION_STATUS');
  }
  await recordedDetails(page.locator('.case-nav .case-details'), item.details);
}

async function assertReloadAndSummary(page, item) {
  const snapshot = prepared(item);
  await page.reload();
  await visible(page.getByRole('heading', { name: '文件準備工作區', exact: true }), 'RELOAD_WORKSPACE_VISIBLE');
  verify(same(prepared(await getCase(page, item.id)), snapshot), 'RELOAD_CONFIRMED_CASE_UNCHANGED');
  verify(await page.evaluate(() => sessionStorage.getItem('cardif-claim-demo-cases-v1')) === null,
    'REAL_API_NO_MOCK_CASE_STORAGE');
  await workspaceConfirmedState(page, item);
  await page.getByRole('button', { name: '查看準備摘要', exact: true }).click();
  await visible(page.getByRole('heading', { name: '送件前準備摘要', exact: true }), 'SUMMARY_VISIBLE');
  verify(await page.locator('.summary-table tbody tr').count() === item.documents.length, 'SUMMARY_DOCUMENT_COUNT');
  await recordedDetails(page.locator('#main-content .case-details'), item.details);
  const surgery = item.documents.find((document) => document.id === 'surgery');
  if (surgery) {
    const row = page.locator('.summary-table tbody tr').filter({ has: page.locator('td').filter({ hasText: surgery.title }) });
    const expected = surgery.status === 'not_applicable' ? '已確認不適用' : surgery.status === 'not_started' ? '尚未準備' : null;
    if (expected) verify((await row.locator('td').nth(2).textContent()).includes(expected), 'SUMMARY_CURRENT_SURGERY_STATUS');
  }
  verify(same(prepared(await getCase(page, item.id)), snapshot), 'SUMMARY_CONFIRMED_CASE_UNCHANGED');
  await layout(page);
  await page.getByRole('button', { name: '返回工作區', exact: true }).click();
}

async function desktopIntake(page) {
  await startGuided(page);
  let result = await ask(page, { message: '這是合成測試。媽媽因疾病在10/14住院，不是意外，10/16接受膽囊切除手術，還沒出院。保單商品代碼是 IHI_C_1131001 和 IHO_1131001，版本都不知道。' });
  realModel(result.response);
  noGuidedMutation(result, page.__feedback.patches);
  verify(result.response.response_type === 'clarification' && result.response.pending_question?.kind === 'fact'
    && result.response.pending_question.field === 'payment_method', 'MOM_ASK_ONLY_UNKNOWN_PAYMENT');
  verify(result.case.dialogue_state.facts.cause === 'illness'
    && result.case.dialogue_state.facts.inpatient === 'yes'
    && result.case.dialogue_state.facts.surgery === 'yes', 'MOM_EXPLICIT_MEDICAL_FACTS');
  const details = result.case.dialogue_state.details;
  verify(details.insured_relation === 'parent', 'MOM_PARENT_RELATION');
  verify(details.visit_dates.admission === '10/14' && details.surgery_date === '10/16',
    'MOM_PARTIAL_DATES_WITHOUT_INVENTED_YEAR');
  verify(details.visit_dates.discharge === null && details.visit_dates.discharge_pending === true,
    'MOM_DISCHARGE_REMAINS_UNKNOWN');
  verify(details.surgery_name === '膽囊切除' || details.surgery_name === '膽囊切除手術', 'MOM_EXPLICIT_SURGERY_NAME');
  verify(details.diagnosis_name === null, 'MOM_NO_DIAGNOSIS_INFERRED_FROM_SURGERY');
  verify(same(details.policy_products.map((item) => item.code).sort(), ['IHI_C_1131001', 'IHO_1131001'].sort())
    && details.policy_products.every((item) => item.verification_status === 'unverified' && item.version === null),
  'MOM_TWO_UNVERIFIED_PRODUCTS_WITHOUT_INVENTED_VERSION');
  verify(result.case.details.insured_relation === 'unknown' && result.case.details.policy_products.length === 0,
    'MOM_EXTRACTED_DETAILS_AWAIT_CONFIRMATION');
  verify(await page.locator('fieldset.guided-type-picker').count() === 0, 'MOM_NO_PREMATURE_CANDIDATE');

  result = await ask(page, { id: result.case.id, quickValue: 'remittance', pending: result.response.pending_question });
  noGuidedMutation(result, page.__feedback.patches);
  const item = await buildGuided(page, result);
  verify(item.conditions.cause === 'illness' && item.conditions.surgery === 'yes'
    && item.conditions.payment_method === 'remittance', 'MOM_CONFIRMED_CONDITIONS');
  verify(same(item.details, result.response.proposed_case_updates.details), 'MOM_CONFIRMED_EXTRACTED_DETAILS');
  verify(item.documents.find((document) => document.id === 'passbook')?.applicability === true,
    'MOM_REMITTANCE_CHECKLIST_RECALCULATED');
  const caseOptions = page.locator('details.case-options');
  await caseOptions.locator(':scope > summary').click();
  await caseOptions.locator('.case-details > summary').click();
  const recorded = await caseOptions.locator('.case-details').textContent();
  verify(recorded.includes('10/14') && recorded.includes('10/16') && recorded.includes('膽囊切除')
    && recorded.includes('尚未出院／待確認'), 'MOM_RECORDED_DETAILS_RENDERED');
  verify(await caseOptions.locator('.product-record').count() === 2
    && (await caseOptions.locator('.product-record').allTextContents()).every((text) => text.includes('使用者提供／待查證')),
  'MOM_PRODUCTS_RENDERED_UNVERIFIED');
  await assertReloadAndSummary(page, item);

  await openAssistant(page);
  for (const message of ['這次可以賠多少錢？請告訴我給付金額。', '今天臺北天氣會下雨嗎？']) {
    const before = prepared(await getCase(page, item.id));
    const patches = page.__feedback.patches;
    const safe = await ask(page, { id: item.id, message, workspace: true });
    verify(safe.response.response_type === 'uncertain' && safe.response.requires_human_review === true,
      'OUT_OF_SCOPE_EXPLICIT_UNCERTAINTY');
    verify(Object.keys(safe.response.proposed_case_updates).length === 0 && !safe.response.proposal
      && safe.response.suggested_claim_types.length === 0, 'OUT_OF_SCOPE_NO_PROPOSAL');
    verify(same(prepared(safe.case), before) && page.__feedback.patches === patches, 'OUT_OF_SCOPE_NO_CASE_MUTATION');
    verify(/無法確認|超出|服務範圍|不能/.test(safe.response.message), 'OUT_OF_SCOPE_SAFE_DIRECT_ANSWER');
    verify(!/(?:可|會|將|能|一定|保證)(?:以)?(?:賠|獲賠|給付)\s*[新臺台幣$\d一二三四五六七八九十百千萬]/.test(safe.response.message),
      'OUT_OF_SCOPE_NO_FABRICATED_BENEFIT');
  }
  await health(page, true);
}

async function proposal(page, result) {
  realModel(result.response);
  verify(result.response.response_type === 'case_update_proposal', 'CORRECTION_EXPLICIT_PROPOSAL');
  verify(uuid4.test(result.response.proposal?.id)
    && result.response.proposal.base_revision === result.case.revision, 'CORRECTION_CURRENT_PROPOSAL_REVISION');
  verify(result.response.proposal.changes.some((change) => change.field === 'conditions.surgery'
    && change.before === 'no' && change.after === 'yes'), 'CORRECTION_SURGERY_BEFORE_AFTER');
  verify(result.response.proposed_case_updates.conditions?.surgery === 'yes', 'CORRECTION_PROPOSED_SURGERY');
  officialReferences(result.response.source_references);
  const card = page.getByRole('region', { name: '案件變更提案', exact: true });
  await visible(card, 'CORRECTION_DIFF_VISIBLE');
  const row = card.locator('dl > div').filter({ has: page.locator('dt', { hasText: /^手術$/ }) });
  verify(await row.count() === 1, 'CORRECTION_SURGERY_DIFF_ROW');
  verify((await row.locator('dd > span').textContent()).trim() === '沒有'
    && (await row.locator('dd > strong').textContent()).trim() === '有', 'CORRECTION_DIFF_HAS_BEFORE_AND_AFTER');
  return card;
}

async function actOnProposal(page, result, action) {
  const path = `/api/v1/cases/${result.case.id}`;
  const saved = page.waitForResponse((response) => responseIs(response, path, 'PATCH'));
  await page.getByRole('button', { name: action === 'accept' ? '確認更新' : '取消變更', exact: true }).click();
  const response = await saved;
  verify(response.status() === 200, 'PROPOSAL_PATCH_SUCCESS');
  const payload = response.request().postDataJSON();
  verify(payload.proposal_id === result.response.proposal.id && payload.expected_revision === result.case.revision
    && payload.proposal_action === action, 'PROPOSAL_PATCH_EXPLICIT_CURRENT_ACTION');
  return response.json();
}

async function tabletCorrection(page) {
  const original = await startDirect(page);
  const snapshot = prepared(original);
  await openAssistant(page);
  let result = await ask(page, { id: original.id, message: '更正，這次其實有接受手術。', workspace: true });
  await proposal(page, result);
  verify(same(prepared(result.case), snapshot) && page.__feedback.patches === 0, 'CORRECTION_AWAITS_CONFIRMATION');
  let item = await actOnProposal(page, result, 'reject');
  verify(same(prepared(item), snapshot), 'CORRECTION_CANCEL_PRESERVES_CONFIRMED_CASE');
  verify(item.dialogue_state.pending_question?.field === 'correction', 'CORRECTION_CANCEL_ASKS_WHAT_DIFFERS');
  await assertReloadAndSummary(page, item);
  await openAssistant(page);

  result = await ask(page, { id: original.id, message: '更正，這次有接受手術，請改成有手術。', workspace: true });
  await proposal(page, result);
  verify(same(prepared(result.case), snapshot) && page.__feedback.patches === 1, 'SECOND_CORRECTION_STILL_AWAITS_CONFIRMATION');
  item = await actOnProposal(page, result, 'accept');
  verify(item.conditions.surgery === 'yes' && item.conditions.cause === 'illness', 'CORRECTION_ACCEPT_UPDATES_ONLY_STATED_FACT');
  const surgeryBefore = original.documents.find((document) => document.id === 'surgery');
  const surgeryAfter = item.documents.find((document) => document.id === 'surgery');
  verify(surgeryBefore?.applicability === false && surgeryAfter?.applicability === null
    && surgeryAfter?.status === 'not_started', 'CORRECTION_ACCEPT_RECALCULATES_SURGERY_DOCUMENT');
  officialChecklist(item);
  verify(page.__feedback.patches === 2, 'CORRECTION_EXACTLY_CANCEL_AND_ACCEPT_PATCHES');
  await assertReloadAndSummary(page, item);
  await openAssistant(page);

  const beforeAnswer = prepared(await getCase(page, original.id));
  const answer = await ask(page, { id: original.id, message: '保險金申請書的申請人簽名和日期可以先空白嗎？請直接說明要怎麼準備。', workspace: true });
  realModel(answer.response);
  verify(answer.response.response_type === 'answer', 'DOCUMENT_SPECIFIC_ANSWER');
  officialReferences(answer.response.source_references);
  verify(answer.response.source_references.some((source) => source.source_id === 'cardif-application'
    && source.page_number === 1), 'DOCUMENT_REFERENCES_RELEVANT_APPLICATION_PAGE');
  verify(answer.response.message.startsWith('直接回答：') && answer.response.message.includes('適用條件：')
    && answer.response.message.includes('來源 [1]'), 'DOCUMENT_ANSWER_CONDITIONS_AND_EVIDENCE_STRUCTURE');
  const directAnswer = answer.response.message.split('\n')[0];
  verify(/申請人簽名/.test(directAnswer) && /日期/.test(directAnswer)
    && /填妥|填寫|填齊/.test(directAnswer),
  'DOCUMENT_DIRECT_SIGNATURE_AND_DATE_GUIDANCE');
  verify(/空白|漏填|留白|填妥|填寫|填齊|簽署日期/.test(answer.response.message),
    'DOCUMENT_ANSWERS_EMPTY_FIELDS_QUESTION');
  verify(!/可以(?:先)?(?:保持|留)?空白|不(?:用|需|必).{0,6}(?:簽名|簽署|填寫日期)/.test(answer.response.message),
    'DOCUMENT_NO_UNSUPPORTED_BLANK_SIGNATURE_PERMISSION');
  verify(Object.keys(answer.response.proposed_case_updates).length === 0 && !answer.response.proposal
    && same(prepared(answer.case), beforeAnswer) && page.__feedback.patches === 2, 'DOCUMENT_ANSWER_DOES_NOT_CHANGE_CASE');
  const bubble = page.getByRole('log', { name: '工作區對話', exact: true }).locator('.bubble:not(.user)').last();
  verify(await bubble.locator('.references a').count() > 0, 'DOCUMENT_UI_CITATIONS_VISIBLE');
  await health(page, true);
}

async function mobileShortAnswers(page) {
  await startGuided(page);
  let result = await ask(page, { message: '這是合成測試。媽媽因為疾病想準備理賠資料，就醫情形請一步一步問我。' });
  realModel(result.response);
  noGuidedMutation(result, page.__feedback.patches);
  verify(result.response.response_type === 'clarification' && result.response.pending_question?.field === 'care_setting'
    && result.response.pending_question.kind === 'fact', 'SHORT_INITIAL_SINGLE_CARE_QUESTION');
  verify(result.case.dialogue_state.facts.inpatient === 'unknown', 'SHORT_NO_ASSUMED_ADMISSION');

  // 短答本身透過輸入框送出，以確實驗證「有」而非較長的「有住院」文案。
  result = await ask(page, { id: result.case.id, message: '有' });
  realModel(result.response);
  noGuidedMutation(result, page.__feedback.patches);
  verify(result.case.dialogue_state.facts.inpatient === 'yes'
    && result.case.dialogue_state.facts.surgery === 'unknown', 'SHORT_YES_ONLY_BINDS_ADMISSION');
  verify(result.response.pending_question?.field === 'surgery' && result.response.pending_question.kind === 'fact',
    'SHORT_PROGRESS_TO_SURGERY_QUESTION');

  result = await ask(page, { id: result.case.id, message: '沒有' });
  realModel(result.response);
  noGuidedMutation(result, page.__feedback.patches);
  verify(result.case.dialogue_state.facts.inpatient === 'yes'
    && result.case.dialogue_state.facts.surgery === 'no', 'SHORT_NO_ONLY_BINDS_SURGERY');
  verify(result.response.pending_question?.field === 'payment_method'
    && result.response.pending_question.kind === 'fact', 'SHORT_PROGRESS_TO_PAYMENT_QUESTION');

  result = await ask(page, { id: result.case.id, quickValue: 'unknown', pending: result.response.pending_question });
  realModel(result.response);
  noGuidedMutation(result, page.__feedback.patches);
  verify(result.case.dialogue_state.deferred_fields.includes('payment_method')
    && result.case.dialogue_state.conditions.payment_method === 'unknown', 'SHORT_UNKNOWN_PAYMENT_DEFERRED');
  const item = await buildGuided(page, result);
  verify(item.conditions.cause === 'illness' && item.conditions.surgery === 'no'
    && item.conditions.payment_method === 'unknown', 'SHORT_CONFIRMED_FACTS_AND_UNKNOWN_PRESERVED');
  verify(item.documents.find((document) => document.id === 'passbook')?.applicability === null,
    'SHORT_DEFERRED_PAYMENT_DOCUMENT_REMAINS_UNCERTAIN');
  await assertReloadAndSummary(page, item);
  await health(page, true);
}

test.beforeEach(async ({ page }) => {
  page.__feedback = { ids: new Set(), discoveries: [], messagePosts: 0, patches: 0, browserErrors: 0, budgetBlocked: false };
  page.on('pageerror', () => { page.__feedback.browserErrors += 1; });
  page.on('console', (message) => { if (message.type() === 'error') page.__feedback.browserErrors += 1; });
  page.on('request', (request) => {
    if (request.method() === 'PATCH' && casePath.test(new URL(request.url()).pathname)) page.__feedback.patches += 1;
  });
  // 初次訊息即使中途失敗，也必須追蹤已建立的合成案，最後逐案刪除。
  page.on('response', (response) => {
    if (!responseIs(response, '/api/v1/cases', 'POST') || response.status() !== 201) return;
    const discovery = response.json().then((item) => {
      if (uuid4.test(item?.id)) page.__feedback.ids.add(item.id);
    }).catch(() => {});
    page.__feedback.discoveries.push(discovery);
  });
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === 'POST' && (messagePath.test(path) || /\/cases\/[^/]+\/messages$/.test(path))) {
      if (!messagePath.test(path) || page.__feedback.messagePosts >= MAX_MESSAGES_PER_VIEWPORT) {
        page.__feedback.budgetBlocked = true;
        await route.abort('blockedbyclient');
        return;
      }
      page.__feedback.messagePosts += 1;
    }
    await route.continue();
  });
});

test.afterEach(async ({ page }, testInfo) => {
  testInfo.setTimeout(testInfo.timeout + 120_000);
  await Promise.allSettled(page.__feedback.discoveries);
  let cleaned = 0;
  let cleanupFailures = 0;
  for (const id of page.__feedback.ids) {
    try {
      const deleted = await page.request.delete(`/api/v1/cases/${id}`, { headers, timeout: 30_000 });
      const missing = await page.request.get(`/api/v1/cases/${id}`, { timeout: 30_000 });
      if ([200, 404].includes(deleted.status()) && missing.status() === 404) cleaned += 1;
      else cleanupFailures += 1;
    } catch { cleanupFailures += 1; }
  }
  // 唯一額外輸出為聚合結果；不附模型回覆、對話、用量、cookie或case ID。
  console.log('[feedback-live]', JSON.stringify({
    project: testInfo.project.name,
    result: testInfo.status,
    message_posts: page.__feedback.messagePosts,
    message_budget: MAX_MESSAGES_PER_VIEWPORT,
    cases_created: page.__feedback.ids.size,
    cases_deleted_with_get_404: cleaned,
    cleanup_failures: cleanupFailures,
    unexpected_browser_errors: page.__feedback.browserErrors,
    budget_blocked: page.__feedback.budgetBlocked,
  }));
  verify(cleanupFailures === 0 && cleaned === page.__feedback.ids.size, 'ALL_SYNTHETIC_CASES_DELETED_AND_GET_404');
  verify(page.__feedback.browserErrors === 0, 'NO_UNEXPECTED_BROWSER_ERROR');
  verify(!page.__feedback.budgetBlocked && page.__feedback.messagePosts <= MAX_MESSAGES_PER_VIEWPORT, 'MAX_EIGHT_MESSAGES_PER_VIEWPORT');
});

test('組員回饋真API與真模型分情境驗收', async ({ page }, testInfo) => {
  try {
    await health(page);
    if (testInfo.project.name === 'feedback-desktop-1440') await desktopIntake(page);
    else if (testInfo.project.name === 'feedback-tablet-768') await tabletCorrection(page);
    else if (testInfo.project.name === 'feedback-mobile-390') await mobileShortAnswers(page);
    else throw new AcceptanceFailure('UNKNOWN_PROJECT_SCENARIO');
    await layout(page);
  } catch (error) {
    if (error instanceof AcceptanceFailure) throw error;
    const code = String(error?.message || '').match(/error_code=([A-Z][A-Z0-9_]{0,63})\b/)?.[1];
    throw new AcceptanceFailure(code ? `MESSAGE_JOB_FAILED_${code}` : 'UI_OR_MESSAGE_JOB_OPERATION_FAILED');
  }
});
