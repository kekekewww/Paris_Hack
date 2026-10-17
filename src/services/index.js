export { MockClaimService } from './mock-claim-service.js';
export { ApiClaimService } from './api-claim-service.js';
export { ServiceError } from './service-error.js';

import { MockClaimService } from './mock-claim-service.js';
import { ApiClaimService } from './api-claim-service.js';

export function createClaimService({ mode = import.meta.env?.VITE_SERVICE_MODE ?? 'mock', ...options } = {}) {
  if (mode === 'mock') return new MockClaimService(options);
  if (mode === 'api') return new ApiClaimService(options);
  throw new Error('服務模式必須設定為 mock 或 api。');
}
