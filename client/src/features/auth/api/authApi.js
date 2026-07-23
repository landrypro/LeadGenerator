import { postJson, request } from '../../../shared/api/httpClient'


export const authApi = {
  login(email, password, signal) {
    return postJson('/api/auth/login', { email, password }, {
      signal,
      fallbackMessage: 'La connexion a échoué.',
    })
  },

  me(signal) {
    return request('/api/auth/me', {
      signal,
      fallbackMessage: 'Impossible de restaurer la session.',
    })
  },

  logout(signal) {
    return postJson('/api/auth/logout', {}, {
      signal,
      fallbackMessage: 'La déconnexion a échoué.',
    })
  },
}
