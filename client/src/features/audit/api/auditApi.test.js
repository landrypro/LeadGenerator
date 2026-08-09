import { beforeEach, describe, expect, it, vi } from 'vitest'

import { request } from '../../../shared/api/httpClient'
import { auditApi } from './auditApi'

vi.mock('../../../shared/api/httpClient', () => ({ request: vi.fn() }))


describe('auditApi', () => {
  beforeEach(() => request.mockResolvedValue({ items: [], next_cursor: null }))

  it('encode uniquement les filtres autorisés pour le journal locataire', async () => {
    const signal = new AbortController().signal
    await auditApi.listTenant({
      occurredFrom: '2026-08-01T00:00:00.000Z',
      occurredTo: '2026-08-10T00:00:00.000Z',
      action: 'membership.role_changed',
      entityType: 'membership',
      entityId: 'membership-id',
      actorId: 'actor-id',
      organizationId: 'forbidden',
    }, 'signed-cursor', 50, signal)

    const [path, options] = request.mock.calls[0]
    const url = new URL(path, 'http://test')
    expect(url.pathname).toBe('/api/audit-events')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      limit: '50',
      occurred_from: '2026-08-01T00:00:00.000Z',
      occurred_to: '2026-08-10T00:00:00.000Z',
      cursor: 'signed-cursor',
      action: 'membership.role_changed',
      entity_type: 'membership',
      entity_id: 'membership-id',
      actor_id: 'actor-id',
    })
    expect(options.signal).toBe(signal)
  })

  it('utilise une route plateforme structurellement distincte', async () => {
    await auditApi.listPlatform({
      occurredFrom: '2026-08-01T00:00:00.000Z',
      occurredTo: '2026-08-10T00:00:00.000Z',
      action: '', entityType: '', entityId: '', actorId: '',
    })
    expect(request.mock.calls[0][0]).toContain('/api/platform/audit-events?')
  })
})
