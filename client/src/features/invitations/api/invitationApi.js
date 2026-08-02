import { postJson } from '../../../shared/api/httpClient'


export const invitationApi = {
  preview(token, signal) {
    return postJson('/api/auth/invitations/preview', { token }, {
      signal,
      fallbackMessage: 'Impossible de vérifier cette invitation.',
    })
  },

  acceptNewAccount(token, displayName, password) {
    return postJson('/api/auth/invitations/accept', {
      token,
      new_account: { display_name: displayName, password },
    }, { fallbackMessage: 'Impossible d’accepter cette invitation.' })
  },

  acceptExistingAccount(token) {
    return postJson('/api/auth/invitations/accept', { token }, {
      fallbackMessage: 'Impossible d’accepter cette invitation.',
    })
  },
}
