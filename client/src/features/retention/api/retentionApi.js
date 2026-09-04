import { postJson, request } from '../../../shared/api/httpClient'

const idempotencyHeaders = () => ({ 'Idempotency-Key': globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}` })

export const retentionApi = {
  listPolicies: () => request('/api/retention/policies?limit=100'),
  createPolicy: (payload) => postJson('/api/retention/policies', payload),
  activatePolicy: (id, version) => postJson(`/api/retention/policies/${encodeURIComponent(id)}/activate`, { version }),
  listReviews: () => request('/api/retention/reviews?limit=100'),
  listHolds: () => request('/api/retention/holds?limit=100'),
  createHold: (payload) => postJson('/api/retention/holds', payload, { headers: idempotencyHeaders() }),
  releaseHold: (id, payload) => postJson(`/api/retention/holds/${encodeURIComponent(id)}/release`, payload),
  listImports: () => request('/api/import-declarations?limit=100'),
  createImport: (payload) => postJson('/api/import-declarations', payload, { headers: idempotencyHeaders() }),
  cancelImport: (id, version) => postJson(`/api/import-declarations/${encodeURIComponent(id)}/cancel`, { version }),
  archiveImport: (id, payload) => postJson(`/api/import-declarations/${encodeURIComponent(id)}/archive`, payload),
  uploadCsv: (declarationId, file) => request(`/api/import-declarations/${encodeURIComponent(declarationId)}/file`, {
    method: 'PUT', headers: { 'Content-Type': 'text/csv' }, body: file,
  }),
  previewCsv: (sessionId) => request(`/api/csv-imports/${encodeURIComponent(sessionId)}/preview`),
  mapCsv: (sessionId, payload) => request(`/api/csv-imports/${encodeURIComponent(sessionId)}/mapping`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  }),
  validateCsv: (sessionId, version) => postJson(`/api/csv-imports/${encodeURIComponent(sessionId)}/validate`, { version }),
  confirmCsv: (sessionId, version, idempotencyKey) => postJson(
    `/api/csv-imports/${encodeURIComponent(sessionId)}/confirm`,
    { version },
    { headers: { 'Idempotency-Key': idempotencyKey } },
  ),
  listCsvQuarantines: (runId) => request(`/api/csv-import-runs/${encodeURIComponent(runId)}/quarantines`),
}
