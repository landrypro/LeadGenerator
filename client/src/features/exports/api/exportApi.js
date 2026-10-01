import { postJson, request } from '../../../shared/api/httpClient'

export const exportApi = {
  list: (cursor = '') => request(`/api/exports?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`),
  create: (payload, key) => postJson('/api/exports', payload, { headers: { 'Idempotency-Key': key } }),
  get: (id) => request(`/api/exports/${encodeURIComponent(id)}`),
  download: (id) => request(`/api/exports/${encodeURIComponent(id)}/download`, { responseType: 'blob' }),
  listRules: () => request('/api/export-source-rules'),
  createRule: (payload) => postJson('/api/export-source-rules', payload),
  updateRule: (id, payload) => request(`/api/export-source-rules/${encodeURIComponent(id)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  }),
}
