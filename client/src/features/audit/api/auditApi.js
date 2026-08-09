import { request } from '../../../shared/api/httpClient'


export const auditApi = {
  listTenant(filters, cursor = '', limit = 50, signal) {
    return list('/api/audit-events', filters, cursor, limit, signal)
  },

  listPlatform(filters, cursor = '', limit = 50, signal) {
    return list('/api/platform/audit-events', filters, cursor, limit, signal)
  },
}


function list(basePath, filters, cursor, limit, signal) {
  const parameters = new URLSearchParams({
    limit: String(limit),
    occurred_from: filters.occurredFrom,
    occurred_to: filters.occurredTo,
  })
  if (cursor) parameters.set('cursor', cursor)
  if (filters.action) parameters.set('action', filters.action)
  if (filters.entityType) parameters.set('entity_type', filters.entityType)
  if (filters.entityId) parameters.set('entity_id', filters.entityId)
  if (filters.actorId) parameters.set('actor_id', filters.actorId)
  return request(`${basePath}?${parameters}`, {
    signal,
    fallbackMessage: 'Impossible de charger le journal d’activité.',
  })
}
