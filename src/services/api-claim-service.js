import { ServiceError } from './service-error.js';

const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const jobIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const invalidJob = () => { throw new ServiceError('INVALID_RESPONSE', '對話工作回傳的資料格式不正確，請稍後重試。'); };

/** HTTP implementation of the shared claim service contract. */
export class ApiClaimService {
  #runtimeHeadersFor;

  constructor({ baseUrl = '/api/v1', timeout = 15000, analysisTimeout = 95000, messageTimeout = 330000, messagePollInterval = 3000, fetchImpl = globalThis.fetch, runtimeHeadersFor = () => ({}) } = {}) {
    // Backslashes can be treated as URL separators by browsers. Keep document
    // uploads on a same-origin path, including when configuration is supplied.
    if (typeof baseUrl !== 'string' || !/^\/(?!\/)/.test(baseUrl) || /[\\?#\s]/.test(baseUrl)) {
      throw new TypeError('API baseUrl 必須是同源的相對路徑。');
    }
    if (typeof fetchImpl !== 'function') {
      throw new TypeError('API 服務需要可使用的 fetch。');
    }
    if (typeof runtimeHeadersFor !== 'function') {
      throw new TypeError('執行期金鑰標頭必須由函式提供。');
    }
    this.#runtimeHeadersFor = runtimeHeadersFor;
    if (!Number.isFinite(timeout) || timeout <= 0) {
      throw new TypeError('API 逾時時間必須大於零。');
    }
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.mode = 'api';
    this.timeout = timeout;
    if (!Number.isFinite(analysisTimeout) || analysisTimeout <= 0) throw new TypeError('文件分析逾時時間必須大於零。');
    this.analysisTimeout = analysisTimeout;
    if (!Number.isFinite(messageTimeout) || messageTimeout <= 0) throw new TypeError('對話逾時時間必須大於零。');
    this.messageTimeout = messageTimeout;
    if (!Number.isFinite(messagePollInterval) || messagePollInterval <= 0) throw new TypeError('對話工作查詢間隔必須大於零。');
    this.messagePollInterval = messagePollInterval;
    // 瀏覽器原生 fetch 必須使用 Window/Worker receiver，不能把服務物件當作 this。
    this.fetchImpl = fetchImpl.bind(globalThis);
  }

  async request(path, { method = 'GET', json, formData, timeoutMs = this.timeout, expectedStatus } = {}) {
    const controller = new AbortController();
    const url = `${this.baseUrl}${path}`;
    const headers = { ...this.#runtimeHeadersFor(url, method), Accept: 'application/json' };
    const options = {
      method,
      headers,
      signal: controller.signal,
      credentials: 'same-origin',
      mode: 'same-origin',
      redirect: 'error',
    };
    if (json !== undefined) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(json);
    } else if (formData !== undefined) {
      // The browser supplies the multipart boundary with the Content-Type.
      options.body = formData;
    }

    let timer;
    try {
      const timeout = new Promise((_resolve, reject) => {
        timer = setTimeout(() => {
          reject(new ServiceError('TIMEOUT', '服務回應逾時，請稍後重試。'));
          controller.abort();
        }, timeoutMs);
      });
      const request = async () => {
        const response = await this.fetchImpl(url, options);
        if (response.ok && expectedStatus !== undefined && response.status !== expectedStatus) {
          throw new ServiceError('INVALID_RESPONSE', '服務回傳了非預期的 HTTP 狀態，請稍後重試。', response.status);
        }
        if (response.status === 204 && response.ok) return null;
        let data;
        try {
          data = await response.json();
        } catch {
          if (!response.ok) {
            throw new ServiceError('HTTP_ERROR', '服務暫時無法完成操作，請稍後重試。', response.status);
          }
          throw new ServiceError('INVALID_RESPONSE', '服務回傳的資料格式不正確，請稍後重試。', response.status);
        }
        if (!response.ok) {
          throw new ServiceError(
            data?.error?.code || 'HTTP_ERROR',
            data?.error?.message || '服務暫時無法完成操作，請稍後重試。',
            response.status,
          );
        }
        return data;
      };
      return await Promise.race([request(), timeout]);
    } catch (error) {
      if (error instanceof ServiceError) throw error;
      throw new ServiceError('NETWORK_ERROR', '無法連線至服務，請確認網路後重試。');
    } finally {
      clearTimeout(timer);
    }
  }

  health() {
    return this.request('/health');
  }

  getClaimTypes() {
    return this.request('/claim-types');
  }

  getLibrary({ query = '', category = 'all' } = {}) {
    return this.request(`/library?${new URLSearchParams({ query, category })}`);
  }

  getFaq() {
    return this.request('/faq');
  }

  getProduct(code) {
    return this.request(`/products/${encodeURIComponent(code)}`);
  }

  createCase(body) {
    return this.request('/cases', { method: 'POST', json: body });
  }

  getCase(id) {
    return this.request(`/cases/${encodeURIComponent(id)}`);
  }

  updateCase(id, body) {
    return this.request(`/cases/${encodeURIComponent(id)}`, { method: 'PATCH', json: body });
  }

  async sendMessage(id, message, { document_id } = {}) {
    if (typeof id !== 'string' || !id.trim() || id === '.' || id === '..') {
      throw new ServiceError('VALIDATION_ERROR', '請提供有效的案件識別碼。', 422);
    }
    const deadline = Date.now() + this.messageTimeout;
    const remaining = () => {
      const milliseconds = deadline - Date.now();
      if (milliseconds <= 0) throw new ServiceError('TIMEOUT', '對話等待逾時，請稍後重試。');
      return milliseconds;
    };
    const requestBudget = () => Math.min(this.timeout, 15000, remaining());
    const path = `/cases/${encodeURIComponent(id)}/message-jobs`;
    // Creation is never retried here: a lost response may still have started
    // the provider request. Only the caller can explicitly start a new attempt.
    const created = await this.request(path, {
      method: 'POST',
      json: { message, ...(document_id === undefined ? {} : { document_id }) },
      timeoutMs: requestBudget(),
      expectedStatus: 202,
    });
    remaining();
    if (!isObject(created) || typeof created.id !== 'string' || !jobIdPattern.test(created.id)
      || created.status !== 'pending' || created.result != null || created.error != null) invalidJob();
    const jobId = created.id;
    while (true) {
      let sleepTimer;
      try {
        await new Promise(resolve => { sleepTimer = setTimeout(resolve, Math.min(this.messagePollInterval, remaining())); });
      } finally {
        clearTimeout(sleepTimer);
      }
      const job = await this.request(`${path}/${encodeURIComponent(jobId)}`, {
        timeoutMs: requestBudget(),
        expectedStatus: 200,
      });
      remaining();
      if (!isObject(job) || job.id !== jobId || !['pending', 'succeeded', 'failed'].includes(job.status)) invalidJob();
      if (job.status === 'pending') {
        if (job.result != null || job.error != null) invalidJob();
        continue;
      }
      if (job.status === 'failed') {
        const error = job.error;
        if (job.result != null || !isObject(error) || typeof error.code !== 'string' || !error.code.trim()
          || typeof error.message !== 'string' || !error.message.trim() || !Number.isInteger(error.status)
          || error.status < 400 || error.status > 599) invalidJob();
        throw new ServiceError(error.code, error.message, error.status);
      }
      const result = job.result;
      if (job.error != null || !isObject(result) || !isObject(result.case) || result.case.id !== id
        || !isObject(result.response) || typeof result.response.message !== 'string') invalidJob();
      return result;
    }
  }

  getChecklist(id) {
    return this.request(`/cases/${encodeURIComponent(id)}/checklist`);
  }

  updateDocument(id, docId, body) {
    return this.request(`/cases/${encodeURIComponent(id)}/documents/${encodeURIComponent(docId)}`, {
      method: 'PATCH',
      json: body,
    });
  }

  analyzeDocument(id, docId, file, _options = {}) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request(`/cases/${encodeURIComponent(id)}/documents/${encodeURIComponent(docId)}/analyze`, {
      method: 'POST',
      formData,
      timeoutMs: this.analysisTimeout,
    });
  }

  getSource(id) {
    return this.request(`/sources/${encodeURIComponent(id)}`);
  }

  deleteCase(id) {
    return this.request(`/cases/${encodeURIComponent(id)}`, { method: 'DELETE' });
  }
}
