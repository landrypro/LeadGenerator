import { afterEach, describe, expect, it, vi } from 'vitest'

import { configureHttpSecurity } from '../../../shared/api/httpClient'
import { organizationApi } from './organizationApi'


afterEach(() => {
  configureHttpSecurity()
  vi.unstubAllGlobals()
})


describe('organizationApi', () => {
  it('charge uniquement l’organisation dérivée de la session', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ id: 'organization-1' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await organizationApi.get()

    expect(fetchMock).toHaveBeenCalledWith('/api/organization', expect.objectContaining({
      credentials: 'same-origin',
    }))
  })

  it('envoie une mutation PATCH protégée sans identifiant d’organisation', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ id: 'organization-1' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    configureHttpSecurity({ token: 'csrf-in-memory' })

    await organizationApi.update({ version: 3, name: 'Nouveau nom' })

    expect(fetchMock).toHaveBeenCalledWith('/api/organization', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ version: 3, name: 'Nouveau nom' }),
      headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-in-memory' }),
    }))
    expect(fetchMock.mock.calls[0][1].body).not.toContain('organization_id')
  })

  it('pagine les membres et met à jour une appartenance sans portée injectée', async () => {
    const fetchMock = successfulFetch({ items: [], next_cursor: null })
    vi.stubGlobal('fetch', fetchMock)
    configureHttpSecurity({ token: 'csrf-in-memory' })

    await organizationApi.listMembers('cursor sûr', 25)
    await organizationApi.updateMember('membership-1', { version: 4, role: 'manager' })

    expect(fetchMock.mock.calls[0][0]).toBe('/api/organization/members?limit=25&cursor=cursor+s%C3%BBr')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/organization/members/membership-1')
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ version: 4, role: 'manager' }),
      headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-in-memory' }),
    }))
    expect(fetchMock.mock.calls[1][1].body).not.toContain('organization_id')
  })

  it('crée, renvoie et révoque des invitations avec les commandes attendues', async () => {
    const fetchMock = successfulFetch({ id: 'invitation-1' })
    vi.stubGlobal('fetch', fetchMock)
    configureHttpSecurity({ token: 'csrf-in-memory' })

    await organizationApi.createInvitation({ email: 'alex@example.ca', role: 'sales', invitation_request_id: 'request-1' })
    await organizationApi.resendInvitation('invitation-1', { resend_request_id: 'request-2' })
    await organizationApi.revokeInvitation('invitation-1')

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/organization/invitations',
      '/api/organization/invitations/invitation-1/resend',
      '/api/organization/invitations/invitation-1',
    ])
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: 'POST' }))
    expect(fetchMock.mock.calls[1][1].body).toBe(JSON.stringify({ resend_request_id: 'request-2' }))
    expect(fetchMock.mock.calls[2][1]).toEqual(expect.objectContaining({ method: 'DELETE', body: '{}' }))
    for (const [, options] of fetchMock.mock.calls) {
      expect(options.headers).toEqual(expect.objectContaining({ 'X-CSRF-Token': 'csrf-in-memory' }))
      expect(options.body).not.toContain('organization_id')
    }
  })
})


function successfulFetch(payload) {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(payload),
  })
}
