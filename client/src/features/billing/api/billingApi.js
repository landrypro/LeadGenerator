import { postJson, request } from '../../../shared/api/httpClient'


export const billingApi = {
  checkoutOptions(signal) {
    return request('/api/billing/checkout-options', {
      signal,
      cache: 'no-store',
      fallbackMessage: 'Impossible de charger les offres de test.',
    })
  },
  currentCatalog(signal) {
    return request('/api/organization/catalog', {
      signal,
      cache: 'no-store',
      fallbackMessage: 'Impossible de consulter le contrat courant.',
    })
  },
  subscription(signal) {
    return request('/api/billing/subscription', {
      signal,
      cache: 'no-store',
      fallbackMessage: 'Impossible de consulter l’état de la facturation.',
    })
  },
  createCheckout(planVersionId, idempotencyKey) {
    return postJson('/api/billing/checkout-session', {
      plan_version_id: planVersionId,
      return_target: 'subscription',
    }, {
      headers: { 'Idempotency-Key': idempotencyKey },
      fallbackMessage: 'Impossible de créer la session Checkout.',
    })
  },
  resumeCheckout() {
    return postJson('/api/billing/resume-checkout', {}, {
      fallbackMessage: 'Impossible de reprendre la session Checkout.',
    })
  },
  createPortal(idempotencyKey) {
    return postJson('/api/billing/portal-session', {
      return_target: 'subscription',
    }, {
      headers: { 'Idempotency-Key': idempotencyKey },
      fallbackMessage: 'Impossible d’ouvrir le portail de facturation.',
    })
  },
}
