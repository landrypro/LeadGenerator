import { postJson, request } from '../../../shared/api/httpClient'


export const prospectApi = {
  list({ cursor = '', limit = 25, includeArchived = false, searchText = '' } = {}, signal) {
    const parameters = new URLSearchParams({ limit: String(limit) })
    if (cursor) parameters.set('cursor', cursor)
    if (includeArchived) parameters.set('include_archived', 'true')
    if (searchText.trim()) parameters.set('search_text', searchText.trim())
    return request(`/api/prospects?${parameters}`, {
      signal,
      fallbackMessage: 'Impossible de charger les prospects.',
    })
  },

  create(payload, signal) {
    return postJson('/api/prospects', payload, {
      signal,
      fallbackMessage: 'Impossible de créer le prospect.',
    })
  },

  get(prospectId, signal) {
    return request(`/api/prospects/${encodeURIComponent(prospectId)}`, { signal, fallbackMessage: 'Impossible de charger le prospect.' })
  },

  update(prospectId, payload, signal) {
    return request(`/api/prospects/${encodeURIComponent(prospectId)}`, {
      method: 'PATCH', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      fallbackMessage: 'Impossible de modifier le profil.',
    })
  },

  listContacts(prospectId, signal) {
    return request(`/api/prospects/${encodeURIComponent(prospectId)}/contacts`, { signal, fallbackMessage: 'Impossible de charger les contacts.' })
  },

  listChannels(prospectId, signal) {
    return request(`/api/prospects/${encodeURIComponent(prospectId)}/channels`, { signal, fallbackMessage: 'Impossible de charger les canaux.' })
  },

  listContactChannels(contactId, signal) {
    return request(`/api/contacts/${encodeURIComponent(contactId)}/channels`, { signal, fallbackMessage: 'Impossible de charger les canaux du contact.' })
  },

  createContact(prospectId, payload, signal) {
    return postJson(`/api/prospects/${encodeURIComponent(prospectId)}/contacts`, payload, { signal, fallbackMessage: 'Impossible d’ajouter le contact.' })
  },

  createChannel(payload, signal) {
    return postJson('/api/contact-channels', payload, { signal, fallbackMessage: 'Impossible d’ajouter le canal.' })
  },

  getPermission(channelId, signal) {
    return request(`/api/contact-channels/${encodeURIComponent(channelId)}/permission`, { signal, fallbackMessage: 'Impossible de charger la permission.' })
  },

  updatePermission(channelId, payload, signal) {
    return request(`/api/contact-channels/${encodeURIComponent(channelId)}/permission`, {
      method: 'PATCH', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      fallbackMessage: 'Impossible de modifier la permission.',
    })
  },
}
