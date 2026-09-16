import { postJson, request } from '../../../shared/api/httpClient'


export const leadSearchApi = {
  health(signal) {
    return request('/api/health', { signal, fallbackMessage: 'Impossible de vérifier la configuration.' })
  },

  search(payload, signal) {
    return postJson('/api/google/places/search', payload, {
      signal,
      fallbackMessage: 'La recherche a échoué.',
    })
  },

  mapSnapshot(token, signal) {
    return postJson('/api/map/snapshot', { token }, {
      signal,
      responseType: 'blob',
      fallbackMessage: 'La carte Google est indisponible.',
    })
  },

  addGoogleProspects(payload, signal) {
    return postJson('/api/prospects/from-google', payload, {
      signal,
      fallbackMessage: 'L’ajout au CRM a échoué.',
    })
  },
}
