import { postJson, request } from '../../../shared/api/httpClient'


export const leadSearchApi = {
  suggestLocation(payload, signal) {
    return postJson('/api/google/places/locations/suggest', payload, { signal, fallbackMessage: 'La recherche de lieu a échoué.' })
  },

  resolveLocation(payload, signal) {
    return postJson('/api/google/places/locations/resolve', payload, { signal, fallbackMessage: 'Le lieu n’a pas pu être sélectionné.' })
  },
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
