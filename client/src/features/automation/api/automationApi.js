import { postJson, request } from '../../../shared/api/httpClient'


export const automationApi = {
  getSettings(signal) {
    return request('/api/automation/settings', {
      signal,
      fallbackMessage: 'Impossible de charger les paramètres Automation.',
    })
  },
  updateSettings(automationEnabled, expectedVersion, signal) {
    return request('/api/automation/settings', {
      method: 'PATCH',
      signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        schema_version: 1,
        automation_enabled: automationEnabled,
        expected_version: expectedVersion,
      }),
      fallbackMessage: 'Impossible de modifier les paramètres Automation.',
    })
  },
  recordSurfaceOpened(surface, signal) {
    return postJson('/api/automation/telemetry/surfaces', { schema_version: 1, surface }, {
      signal,
      fallbackMessage: 'Impossible d’enregistrer la navigation Automation.',
    })
  },
  listPlaybooks(signal) {
    return request('/api/automation/playbooks', {
      signal,
      fallbackMessage: 'Impossible de charger les Playbooks.',
    })
  },
  listExceptions(signal) {
    return request('/api/automation/exceptions', {
      signal,
      fallbackMessage: 'Impossible de charger les entrées et exceptions.',
    })
  },
  transitionException(id, command, version, idempotencyKey, { resolutionCode, signal } = {}) {
    const body = { schema_version: 1, idempotency_key: idempotencyKey }
    if (resolutionCode) body.resolution_code = resolutionCode
    return postJson(`/api/automation/exceptions/${encodeURIComponent(id)}/${command}`, body, {
      signal,
      headers: { 'If-Match': `"${version}"` },
      fallbackMessage: 'Impossible de traiter l’exception.',
    })
  },
  runPreflight(code, idempotencyKey, signal) {
    return postJson(`/api/automation/playbooks/${encodeURIComponent(code)}/preflights`, {
      schema_version: 1,
      idempotency_key: idempotencyKey,
    }, {
      signal,
      fallbackMessage: 'Impossible de lancer le Prévol.',
    })
  },
  transitionPlaybook(code, command, version, idempotencyKey, { reasonCode, signal } = {}) {
    const body = { schema_version: 1, idempotency_key: idempotencyKey }
    if (reasonCode) body.reason_code = reasonCode
    return postJson(`/api/automation/playbooks/${encodeURIComponent(code)}/${command}`, body, {
      signal,
      headers: { 'If-Match': `"${version}"` },
      fallbackMessage: 'Impossible de modifier le Playbook.',
    })
  },
  createPlan(payload, signal) {
    return postJson('/api/automation/intent-plans', { schema_version: 1, ...payload }, {
      signal,
      fallbackMessage: 'Impossible de préparer le plan.',
    })
  },
}
