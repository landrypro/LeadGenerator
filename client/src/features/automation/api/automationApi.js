import { postJson } from '../../../shared/api/httpClient'


export const automationApi = {
  createPlan(payload, signal) {
    return postJson('/api/automation/intent-plans', { schema_version: 1, ...payload }, {
      signal,
      fallbackMessage: 'Impossible de préparer le plan.',
    })
  },
}
