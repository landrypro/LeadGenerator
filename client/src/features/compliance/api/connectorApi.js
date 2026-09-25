import { postJson, request } from '../../../shared/api/httpClient'

export const connectorApi = {
  list(signal) {
    return request('/api/provider-connectors', { signal, fallbackMessage: 'Impossible de charger les connecteurs.' })
  },
  create(payload, signal) {
    return postJson('/api/provider-connectors', payload, { signal, fallbackMessage: 'Impossible de créer le connecteur.' })
  },
  submit(id, version, signal) {
    return postJson(`/api/provider-connectors/${encodeURIComponent(id)}/submit-review`, { version }, { signal, fallbackMessage: 'Impossible de soumettre la revue.' })
  },
  review(id, payload, signal) {
    return postJson(`/api/provider-connectors/${encodeURIComponent(id)}/review`, payload, { signal, fallbackMessage: 'Impossible d’enregistrer la revue.' })
  },
  disable(id, bindingId, signal) {
    return postJson(`/api/provider-connectors/${encodeURIComponent(id)}/bindings/${encodeURIComponent(bindingId)}/disable`, {}, { signal, fallbackMessage: 'Impossible de désactiver le connecteur.' })
  },
}
