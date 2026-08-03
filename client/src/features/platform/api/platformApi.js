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
}


function post(path, payload, signal, fallbackMessage) {
  return request(path, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), fallbackMessage,
  })
}


function pagePath(basePath, cursor, limit) {
  const parameters = new URLSearchParams({ limit: String(limit) })
  if (cursor) parameters.set('cursor', cursor)
  return `${basePath}?${parameters}`
}
