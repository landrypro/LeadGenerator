import { request } from '../../../shared/api/httpClient'


export const usageApi = {
  current(scope = 'self', signal) {
    return request(`/api/usage/current?scope=${encodeURIComponent(scope)}`, {
      signal, cache: 'no-store', fallbackMessage: 'Impossible de charger le quota courant.',
    })
  },
  report(filters, signal) {
    const params = new URLSearchParams({ period: filters.period, scope: filters.scope, group_by: 'day' })
    if (filters.period === 'custom') {
      params.set('start_on', filters.start_on)
      params.set('end_on', filters.end_on)
    }
    if (filters.scope === 'owner') params.set('owner_membership_id', filters.owner_membership_id)
    return request(`/api/usage/report?${params}`, {
      signal, cache: 'no-store', fallbackMessage: 'Impossible de charger le rapport d’usage.',
    })
  },
}
