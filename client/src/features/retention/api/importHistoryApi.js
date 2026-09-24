import { request } from '../../../shared/api/httpClient'

function historyPath(base, cursor, filters) {
  const params = new URLSearchParams({ limit: '25' })
  if (cursor) params.set('cursor', cursor)
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value)
  return `${base}?${params}`
}

export const importHistoryApi = {
  runs: (cursor = '', filters = {}) => request(historyPath('/api/csv-import-runs', cursor, filters)),
  sessions: (cursor = '', filters = {}) => request(historyPath('/api/csv-import-sessions', cursor, filters)),
  run: (id) => request(`/api/csv-import-runs/${encodeURIComponent(id)}`),
  quarantines: (id, afterLine = 0) => request(`/api/csv-import-runs/${encodeURIComponent(id)}/quarantines?limit=25&after_line=${afterLine}`),
}
