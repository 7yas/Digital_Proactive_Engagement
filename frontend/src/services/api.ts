const BASE = 'http://localhost:8000/api';

async function req(path: string, opts: RequestInit = {}) {
  const response = await fetch(BASE + path, {
    headers: {
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
    ...opts,
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

export const api = {
  customers: (query = '') =>
    req('/customers' + query),

  customer: (id: string) =>
    req('/customers/' + encodeURIComponent(id)),

  pipeline: (id: string) =>
    req(
      '/run-pipeline/' +
      encodeURIComponent(id),
      {
        method: 'POST',
      }
    ),

  // NEW: Customer-specific AI chatbot
  customerChat: (
    id: string,
    message: string,
    conversation: any[]
  ) =>
    req(
      '/customers/' +
      encodeURIComponent(id) +
      '/chat',
      {
        method: 'POST',
        body: JSON.stringify({
          message,
          conversation,
        }),
      }
    ),

  analytics: () =>
    req('/analytics'),

  decisions: () =>
    req('/decisions'),

  engagements: () =>
    req('/engagements'),

  escalations: () =>
    req('/escalations'),

  audit: () =>
    req('/audit-logs'),

  signals: () =>
    req('/signals'),

  datasetInfo: () =>
    req('/dataset-info'),

  aiStatus: () =>
    req('/ai-status'),
};