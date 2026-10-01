import { postJson, request } from '../../../shared/api/httpClient'

function queryFor(filters = {}) {
  const parameters = new URLSearchParams({ limit: String(filters.limit ?? 25) })
  if (filters.cursor) parameters.set('cursor', filters.cursor)
  if (filters.q?.trim()) parameters.set('q', filters.q.trim())
  for (const stage of filters.stages ?? []) parameters.append('stage', stage)
  if (filters.currencyCode) parameters.set('currency_code', filters.currencyCode)
  if (filters.overdue) parameters.set('overdue', 'true')
  if (filters.prospectId) parameters.set('prospect_id', filters.prospectId)
  return parameters
}

export const opportunityApi = {
  list(filters = {}, signal) {
    return request(`/api/opportunities?${queryFor(filters)}`, { signal, fallbackMessage: 'Impossible de charger les opportunités.' })
  },

  listForProspect(prospectId, filters = {}, signal) {
    return request(`/api/prospects/${encodeURIComponent(prospectId)}/opportunities?${queryFor(filters)}`, { signal, fallbackMessage: 'Impossible de charger les opportunités.' })
  },

  summaries(prospectIds, signal) {
    const parameters = new URLSearchParams()
    for (const prospectId of [...new Set(prospectIds)].slice(0, 100)) parameters.append('prospect_id', prospectId)
    if (!parameters.size) return Promise.resolve({ items: [] })
    return request(`/api/prospects/opportunity-summaries?${parameters}`, { signal, fallbackMessage: 'Impossible de charger les synthèses des opportunités.' })
  },

  create(prospectId, payload, signal) {
    return postJson(`/api/prospects/${encodeURIComponent(prospectId)}/opportunities`, payload, { signal, fallbackMessage: 'Impossible de créer l’opportunité.' })
  },

  update(opportunityId, payload, signal) {
    return request(`/api/opportunities/${encodeURIComponent(opportunityId)}`, { method: 'PATCH', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), fallbackMessage: 'Impossible de modifier l’opportunité.' })
  },

  transition(opportunityId, payload, signal) {
    return postJson(`/api/opportunities/${encodeURIComponent(opportunityId)}/stage-transitions`, payload, { signal, fallbackMessage: 'Impossible de changer l’étape de l’opportunité.' })
  },

  reopen(opportunityId, payload, signal) {
    return postJson(`/api/opportunities/${encodeURIComponent(opportunityId)}/reopen`, payload, { signal, fallbackMessage: 'Impossible de réouvrir l’opportunité.' })
  },
}
