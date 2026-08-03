import { request } from '../../../shared/api/httpClient'


export const organizationApi = {
  get(signal) {
    return request('/api/organization', {
      signal,
      fallbackMessage: 'Impossible de charger l’organisation.',
    })
  },

  update(payload, signal) {
    return request('/api/organization', {
      method: 'PATCH',
      signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      fallbackMessage: 'Impossible de modifier l’organisation.',
    })
  },
}
