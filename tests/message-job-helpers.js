import { expect } from '@playwright/test';

const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const jobCollection = /^\/api\/v1\/cases\/([^/]+)\/message-jobs$/;
const jobItem = /^\/api\/v1\/cases\/([^/]+)\/message-jobs\/([^/]+)$/;
const safeErrorCode = (body) => typeof body?.error?.code === 'string'
  && /^[A-Z][A-Z0-9_]{0,63}$/.test(body.error.code) ? body.error.code : 'NO_SAFE_ERROR_CODE';

async function readJSON(response, context) {
  try {
    return await response.json();
  } catch {
    throw new Error(`${context}必須回傳 JSON；不記錄原始回覆內容。`);
  }
}

// 只觀察 UI 的真 POST／GET，不另送 request 輪詢或繞過前端 Adapter。
export async function waitForUIMessageJob(page, {
  caseId = null, context = '對話工作', timeout = 330_000,
} = {}) {
  const queued = [];
  let notify = null;
  let stop;
  const stopped = new Promise((resolve, reject) => { stop = reject; });
  // 同一時限也涵蓋 headers 到達後仍未完成的 JSON body。
  const timer = setTimeout(() => {
    stop(new Error(`${context}未在 ${timeout / 1000} 秒內完成 UI 工作回覆。`));
  }, timeout);
  const capture = (response) => {
    const match = new URL(response.url()).pathname.match(jobItem);
    if (response.request().method() !== 'GET' || !match || (caseId && match[1] !== caseId)) return;
    queued.push(response);
    notify?.();
  };
  const close = () => stop(new Error(`${context}完成前頁面已關閉。`));
  page.on('response', capture);
  page.on('close', close);
  const observe = async () => {
    const started = await page.waitForResponse((response) => {
      const match = new URL(response.url()).pathname.match(jobCollection);
      return response.request().method() === 'POST' && Boolean(match) && (!caseId || match[1] === caseId);
    }, { timeout });
    const accepted = await readJSON(started, context);
    expect(started.status(), `${context}必須建立背景工作；error_code=${safeErrorCode(accepted)}`).toBe(202);
    expect(Boolean(accepted && typeof accepted === 'object'), `${context}必須回傳結構化工作`).toBe(true);
    expect(typeof accepted.id === 'string' && uuid4.test(accepted.id), `${context}必須回傳 UUID4 工作 ID`).toBe(true);
    expect(accepted.status, `${context}建立時必須仍為 pending`).toBe('pending');
    const actualCaseId = new URL(started.url()).pathname.match(jobCollection)[1];
    const path = `/api/v1/cases/${actualCaseId}/message-jobs/${accepted.id}`;
    while (true) {
      if (!queued.length) {
        await new Promise((resolve) => {
          notify = () => {
            notify = null;
            resolve();
          };
        });
      }
      const polled = queued.shift();
      if (new URL(polled.url()).pathname !== path) continue;
      const job = await readJSON(polled, context);
      expect(polled.status(), `${context}輪詢必須成功；error_code=${safeErrorCode(job)}`).toBe(200);
      expect(Boolean(job && typeof job === 'object'), `${context}輪詢必須回傳結構化工作`).toBe(true);
      expect(job.id === accepted.id, `${context}輪詢結果必須對應同一工作 ID`).toBe(true);
      expect(['pending', 'succeeded', 'failed'].includes(job.status), `${context}工作狀態必須符合契約`).toBe(true);
      if (job.status === 'pending') continue;
      if (job.status === 'failed') {
        throw new Error(`${context}背景工作失敗；error_code=${safeErrorCode(job)}`);
      }
      const result = job.result;
      expect(Boolean(result && typeof result === 'object'), `${context}完成時必須包含 result`).toBe(true);
      expect(result.case?.id === actualCaseId, `${context}結果必須屬於建立工作的同一案件`).toBe(true);
      expect(Array.isArray(result.case.messages) && Array.isArray(result.case.documents), `${context}必須回傳案件訊息與文件陣列`).toBe(true);
      const answer = result.response;
      expect(Boolean(answer && typeof answer === 'object'), `${context}完成時必須包含結構化對話回覆`).toBe(true);
      expect(typeof answer.message === 'string' && typeof answer.response_type === 'string'
        && typeof answer.provider === 'string' && typeof answer.is_simulated === 'boolean'
        && typeof answer.requires_human_review === 'boolean', `${context}回覆欄位型別必須符合契約`).toBe(true);
      expect(Array.isArray(answer.source_references) && Array.isArray(answer.suggested_claim_types)
        && Array.isArray(answer.missing_information), `${context}回覆必須保留來源、候選與待確認欄位`).toBe(true);
      expect(Boolean(answer.proposed_case_updates && typeof answer.proposed_case_updates === 'object'
        && !Array.isArray(answer.proposed_case_updates)), `${context}回覆必須包含結構化案件更新建議`).toBe(true);
      return result;
    }
  };
  try {
    return await Promise.race([observe(), stopped]);
  } finally {
    clearTimeout(timer);
    page.off('response', capture);
    page.off('close', close);
  }
}
