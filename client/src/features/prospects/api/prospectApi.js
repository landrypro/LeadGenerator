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

  pipelineBoard({ searchText = '', priority = '' } = {}, signal) {
    const parameters = new URLSearchParams()
    if (searchText.trim()) parameters.set('search_text', searchText.trim())
    if (priority !== '') parameters.set('priority', String(priority))
    const query = parameters.toString()
    return request(`/api/prospects/pipeline/board${query ? `?${query}` : ''}`, { signal, fallbackMessage: 'Impossible de charger le pipeline.' })
  },

  pipelineColumn(stageCode, { cursor = '', searchText = '', priority = '' } = {}, signal) {
    const parameters = new URLSearchParams({ limit: '25' })
    if (cursor) parameters.set('cursor', cursor)
    if (searchText.trim()) parameters.set('search_text', searchText.trim())
    if (priority !== '') parameters.set('priority', String(priority))
    return request(`/api/prospects/pipeline/board/columns/${encodeURIComponent(stageCode)}?${parameters}`, {
      signal,
      fallbackMessage: 'Impossible de charger davantage de prospects.',
    })
  },

  moveStage(prospectId, payload, signal) {
    return postJson(`/api/prospects/${encodeURIComponent(prospectId)}/stage-transitions`, payload, { signal, fallbackMessage: 'Impossible de déplacer le prospect.' })
  },

  reopen(prospectId, payload, signal) {
    return postJson(`/api/prospects/${encodeURIComponent(prospectId)}/reopen`, payload, { signal, fallbackMessage: 'Impossible de réouvrir le prospect.' })
  },

  listStageTransitions(prospectId, signal) {
    return request(`/api/prospects/${encodeURIComponent(prospectId)}/stage-transitions`, { signal, fallbackMessage: 'Impossible de charger l’historique du pipeline.' })
  },

  listTimeline(prospectId, signal) {
    return request(`/api/prospects/${encodeURIComponent(prospectId)}/timeline`, {
      signal,
      fallbackMessage: 'Impossible de charger la chronologie.',
    })
  },

  createActivity(prospectId, payload, signal) {
    return postJson(`/api/prospects/${encodeURIComponent(prospectId)}/activities`, payload, {
      signal,
      fallbackMessage: 'Impossible d’enregistrer l’activité.',
    })
  },

  correctActivity(activityId, payload, signal) {
    return postJson(`/api/prospects/activities/${encodeURIComponent(activityId)}/corrections`, payload, {
      signal,
      fallbackMessage: 'Impossible de corriger l’activité.',
    })
  },

  listTasks({ mine = false, prospectId = '', status = '', dueBefore = '' } = {}, signal) {
    const parameters = new URLSearchParams({ limit: '100' })
    if (mine) parameters.set('mine', 'true')
    if (prospectId) parameters.set('prospect_id', prospectId)
    if (status) parameters.set('status', status)
    if (dueBefore) parameters.set('due_before', dueBefore)
    return request(`/api/prospects/tasks?${parameters}`, { signal, fallbackMessage: 'Impossible de charger les tâches.' })
  },

  listDueReminders({ mine = true } = {}, signal) {
    return request(`/api/prospects/tasks/reminders/due?mine=${mine ? 'true' : 'false'}`, { signal, fallbackMessage: 'Impossible de charger les rappels.' })
  },

  listNextActions(signal) {
    return request('/api/prospects/tasks/next-actions?limit=500', { signal, fallbackMessage: 'Impossible de charger les prochaines actions.' })
  },

  createTask(prospectId, payload, signal) {
    return postJson(`/api/prospects/${encodeURIComponent(prospectId)}/tasks`, payload, { signal, fallbackMessage: 'Impossible de créer la tâche.' })
  },

  updateTask(taskId, payload, signal) {
    return request(`/api/prospects/tasks/${encodeURIComponent(taskId)}`, {
      method: 'PATCH', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      fallbackMessage: 'Impossible de modifier la tâche.',
    })
  },

  taskAction(taskId, action, payload, signal) {
    return postJson(`/api/prospects/tasks/${encodeURIComponent(taskId)}/${encodeURIComponent(action)}`, payload, {
      signal,
      fallbackMessage: 'Impossible de modifier la tâche.',
    })
  },
}
