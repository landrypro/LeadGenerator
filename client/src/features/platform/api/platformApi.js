import { request } from '../../../shared/api/httpClient'


export const platformApi = {
  listOrganizations(cursor = '', limit = 25, signal) {
    return request(pagePath('/api/platform/organizations', cursor, limit), {
      signal,
      fallbackMessage: 'Impossible de charger les organisations de la plateforme.',
    })
  },

  createOrganization(payload, signal) {
    return post('/api/platform/organizations', payload, signal, 'Impossible de créer l’organisation.')
  },

  resendInitialInvitation(organizationId, payload, signal) {
    return post(`/api/platform/organizations/${encodeURIComponent(organizationId)}/first-invitation/resend`, payload, signal, 'Impossible de renvoyer l’invitation initiale.')
  },

  revokeInitialInvitation(organizationId, signal) {
    return post(`/api/platform/organizations/${encodeURIComponent(organizationId)}/first-invitation/revoke`, {}, signal, 'Impossible de révoquer l’invitation initiale.')
  },

  suspendOrganization(organizationId, payload, signal) {
    return post(`/api/platform/organizations/${encodeURIComponent(organizationId)}/suspend`, payload, signal, 'Impossible de suspendre l’organisation.')
  },

  reactivateOrganization(organizationId, payload, signal) {
    return post(`/api/platform/organizations/${encodeURIComponent(organizationId)}/reactivate`, payload, signal, 'Impossible de réactiver l’organisation.')
  },

  listBillingOrganizations({ cursor = '', limit = 25, state = '', source = '' } = {}, signal) {
    const parameters = new URLSearchParams({ limit: String(limit) })
    if (cursor) parameters.set('cursor', cursor)
    if (state) parameters.set('state', state)
    if (source) parameters.set('source', source)
    return request(`/api/platform/billing/organizations?${parameters}`, {
      signal,
      fallbackMessage: 'Impossible de charger la consultation Billing de la plateforme.',
    })
  },

  getBillingOrganization(organizationId, signal) {
    return request(`/api/platform/billing/organizations/${encodeURIComponent(organizationId)}`, {
      signal,
      fallbackMessage: 'Impossible de charger le détail Billing de cette organisation.',
    })
  },

  listManualBillingGrantOptions(signal) {
    return request('/api/platform/billing/manual-grant-options', {
      signal,
      cache: 'no-store',
      fallbackMessage: 'Impossible de charger les forfaits attribuables en sandbox.',
    })
  },

  proposeManualBillingGrant(payload, idempotencyKey, signal) {
    return post('/api/platform/billing/manual-grants', payload, signal, 'Impossible de proposer l’attribution sandbox.', idempotencyKey)
  },

  approveManualBillingGrant(grantId, version, idempotencyKey, signal) {
    return post(`/api/platform/billing/manual-grants/${encodeURIComponent(grantId)}/approve`, { version }, signal,
      'Impossible d’approuver l’attribution sandbox.', idempotencyKey)
  },

  revokeManualBillingGrant(grantId, version, idempotencyKey, signal) {
    return post(`/api/platform/billing/manual-grants/${encodeURIComponent(grantId)}/revoke`, { version }, signal,
      'Impossible de révoquer l’attribution sandbox.', idempotencyKey)
  },
}


function post(path, payload, signal, fallbackMessage, idempotencyKey = '') {
  return request(path, {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}) },
    body: JSON.stringify(payload), fallbackMessage,
  })
}


function pagePath(basePath, cursor, limit) {
  const parameters = new URLSearchParams({ limit: String(limit) })
  if (cursor) parameters.set('cursor', cursor)
  return `${basePath}?${parameters}`
}
