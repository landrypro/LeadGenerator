import { request } from '../../../shared/api/httpClient'


export const dashboardApi = {
  summary(filters, signal) {
    const params = new URLSearchParams({ scope: filters.scope })
    if (filters.scope === 'owner') params.set('owner_membership_id', filters.owner_membership_id)
    if (filters.period === 'custom') {
      params.set('start_on', filters.start_on)
      params.set('end_on', filters.end_on)
    } else {
      params.set('period', filters.period)
    }
    return request(`/api/dashboard/summary?${params}`, {
      signal,
      cache: 'no-store',
      fallbackMessage: 'Impossible de charger le tableau de bord.',
    })
  },
}
