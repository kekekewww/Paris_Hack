const keyPattern = /^sk-or-v1-[a-f0-9]{64}$/;
const casePath = /^\/api\/v1\/cases\/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\/(?:messages|message-jobs)$/i;

function capability(status, origin, key) {
  return Object.freeze({
    status,
    headersFor(url, method = 'GET') {
      if (!key || typeof url !== 'string' || typeof method !== 'string' || /[\\?#\s]/.test(url)) return {};
      try {
        const target = new URL(url, origin);
        if (target.origin !== origin || target.username || target.password) return {};
        const verb = method.toUpperCase();
        if ((verb === 'GET' && target.pathname === '/api/v1/health')
          || (verb === 'POST' && casePath.test(target.pathname))) {
          return { 'X-OpenRouter-Key': key };
        }
      } catch {
        // An invalid destination must never receive the credential.
      }
      return {};
    },
  });
}

/**
 * Read once from the navigation URL and remove it before exposing a capability.
 * The caller owns the returned object for this page's lifetime. The key remains
 * only in its closure: never put this object or its headers in persisted state.
 */
export function consumeRuntimeKey(location, history) {
  let page;
  try {
    page = new URL(location.href);
  } catch {
    return capability('rejected');
  }

  // Work on raw entries so removing key does not re-encode unrelated values,
  // reorder duplicate parameters, or change hash-based application navigation.
  const entries = page.search.slice(1).split('&');
  const keys = [];
  const retained = entries.filter(entry => {
    const parameter = new URLSearchParams(entry);
    if (!parameter.has('key')) return true;
    keys.push(parameter.get('key'));
    return false;
  });
  if (!keys.length) return capability('absent', page.origin);

  const query = retained.length ? '?' + retained.join('&') : '';
  try {
    history.replaceState(history.state, '', page.pathname + query + page.hash);
  } catch {
    // Do not use the key if the browser could not remove it from its URL.
    return capability('rejected', page.origin);
  }
  if (keys.length !== 1 || !keyPattern.test(keys[0]) || !['https:', 'http:'].includes(page.protocol)) {
    return capability('rejected', page.origin);
  }
  return capability('ready', page.origin, keys[0]);
}
