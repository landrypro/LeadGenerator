import { postJson, request } from '../../../shared/api/httpClient'


export const leadSearchApi = {
  health(signal) {
    return request('/api/health', { signal, fallbackMessage: 'Impossible de vérifier la configuration.' })
  },

  /** @deprecated Remplacé en V1 par une recherche Google limitée sans balayage multi-zone. */
  search(payload, signal) {
    return postJson('/api/leads/search', payload, {
      signal,
      fallbackMessage: 'La recherche a échoué.',
    })
  },

  /** @deprecated Remplacé en V1 par l’export des seules données internes du CRM. */
  export(payload) {
    return postJson('/api/leads/export', payload, {
      responseType: 'blob',
      fallbackMessage: 'L’export a échoué.',
    })
  },

  mapSnapshot(token, signal) {
    return postJson('/api/map/snapshot', { token }, {
      signal,
      responseType: 'blob',
      fallbackMessage: 'La carte Google est indisponible.',
    })
  },
}
