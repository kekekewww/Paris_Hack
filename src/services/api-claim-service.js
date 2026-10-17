import { ServiceError } from './service-error.js';

/** HTTP implementation of the shared claim service contract. */
export class ApiClaimService {
  constructor({ baseUrl = '/api/v1', timeout = 15000, analysisTimeout = 95000, messageTimeout = 50000, fetchImpl = globalThis.fetch } = {}) {
    // Backslashes can be treated as URL separators by browsers. Keep document
    // uploads on a same-origin path, including when configuration is supplied.
    if (typeof baseUrl !== 'string' || !/^\/(?!\/)/.test(baseUrl) || /[\\?#\s]/.test(baseUrl)) {
      throw new TypeError('API baseUrl 必須是同源的相對路徑。');
    }
    if (typeof fetchImpl !== 'function') {
      throw new TypeError('API 服務需要可使用的 fetch。');
    }
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
    // 瀏覽器原生 fetch 必須使用 Window/Worker receiver，不能把服務物件當作 this。
    this.fetchImpl = fetchImpl.bind(globalThis);
  }

  async request(path, { method = 'GET', json, formData, timeoutMs = this.timeout } = {}) {
    const controller = new AbortController();
    const headers = { Accept: 'application/json' };
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
        const response = await this.fetchImpl(`${this.baseUrl}${path}`, options);
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

  createCase(body) {
    return this.request('/cases', { method: 'POST', json: body });
  }

  getCase(id) {
    return this.request(`/cases/${encodeURIComponent(id)}`);
  }

  updateCase(id, body) {
    return this.request(`/cases/${encodeURIComponent(id)}`, { method: 'PATCH', json: body });
  }

  sendMessage(id, message, { document_id } = {}) {
    return this.request(`/cases/${encodeURIComponent(id)}/messages`, {
      method: 'POST',
      json: { message, ...(document_id === undefined ? {} : { document_id }) },
      timeoutMs: this.messageTimeout,
    });
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
