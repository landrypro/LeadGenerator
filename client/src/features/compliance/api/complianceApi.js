import { postJson, request } from '../../../shared/api/httpClient'


export const complianceApi = {
  listProviders(signal) {
    return request('/api/source-providers?limit=100', { signal, fallbackMessage: 'Impossible de charger les fournisseurs.' })
  },
  createProvider(payload, signal) {
    return postJson('/api/source-providers', payload, { signal, fallbackMessage: 'Impossible de créer le fournisseur.' })
  },
  updateProvider(providerId, payload, signal) {
    return request(`/api/source-providers/${encodeURIComponent(providerId)}`, {
      method: 'PATCH', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      fallbackMessage: 'Impossible de modifier le fournisseur.',
    })
  },
  listAcquisitions(signal) {
    return request('/api/acquisitions?limit=100', { signal, fallbackMessage: 'Impossible de charger les acquisitions.' })
  },
  declareAcquisition(payload, signal) {
    return postJson('/api/acquisitions', payload, {
      signal, headers: { 'Idempotency-Key': globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}` },
      fallbackMessage: 'Impossible de déclarer l’acquisition.',
    })
  },
  decideAcquisition(acquisitionId, payload, signal) {
    return postJson(`/api/acquisitions/${encodeURIComponent(acquisitionId)}/decision`, payload, { signal, fallbackMessage: 'Impossible d’enregistrer la décision.' })
  },
}
