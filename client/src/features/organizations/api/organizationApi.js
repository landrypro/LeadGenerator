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

  listMembers(cursor = '', limit = 25, signal) {
    return request(pagePath('/api/organization/members', cursor, limit), {
      signal,
      fallbackMessage: 'Impossible de charger les membres.',
    })
  },

  updateMember(membershipId, payload, signal) {
    return request(`/api/organization/members/${encodeURIComponent(membershipId)}`, {
      method: 'PATCH',
      signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      fallbackMessage: 'Impossible de modifier ce membre.',
    })
  },

  listInvitations(cursor = '', limit = 25, signal) {
    return request(pagePath('/api/organization/invitations', cursor, limit), {
      signal,
      fallbackMessage: 'Impossible de charger les invitations.',
    })
  },

  createInvitation(payload, signal) {
    return request('/api/organization/invitations', {
      method: 'POST',
      signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      fallbackMessage: 'Impossible de créer l’invitation.',
    })
  },

  resendInvitation(invitationId, payload, signal) {
    return request(`/api/organization/invitations/${encodeURIComponent(invitationId)}/resend`, {
      method: 'POST',
      signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      fallbackMessage: 'Impossible de renvoyer l’invitation.',
    })
  },

  revokeInvitation(invitationId, signal) {
    return request(`/api/organization/invitations/${encodeURIComponent(invitationId)}`, {
      method: 'DELETE',
      signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
      fallbackMessage: 'Impossible de révoquer l’invitation.',
    })
  },
}


function pagePath(basePath, cursor, limit) {
  const parameters = new URLSearchParams({ limit: String(limit) })
  if (cursor) parameters.set('cursor', cursor)
  return `${basePath}?${parameters}`
}
