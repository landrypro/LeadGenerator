import { afterEach, describe, expect, it, vi } from 'vitest'

import { configureHttpSecurity } from '../../../shared/api/httpClient'
import { platformApi } from './platformApi'


afterEach(() => { configureHttpSecurity(); vi.unstubAllGlobals() })


describe('platformApi', () => {
  it('pagine par curseur avec la limite demandée', async () => {
    const fetchMock = successfulFetch({ items: [], next_cursor: null })
    vi.stubGlobal('fetch', fetchMock)
    await platformApi.listOrganizations('curseur sûr', 25)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/platform/organizations?limit=25&cursor=curseur+s%C3%BBr')
  })

  it('envoie les trois mutations exactes avec CSRF', async () => {
    const fetchMock = successfulFetch({ organization: { id: 'org/1' } })
    vi.stubGlobal('fetch', fetchMock)
    configureHttpSecurity({ token: 'csrf-memory' })
    const create = { name: 'Entreprise', creation_request_id: 'create-1' }
    await platformApi.createOrganization(create)
    await platformApi.resendInitialInvitation('org/1', { resend_request_id: 'resend-1' })
    await platformApi.revokeInitialInvitation('org/1')
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/platform/organizations',
      '/api/platform/organizations/org%2F1/first-invitation/resend',
      '/api/platform/organizations/org%2F1/first-invitation/revoke',
    ])
    expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify(create))
    expect(fetchMock.mock.calls[1][1].body).toBe('{"resend_request_id":"resend-1"}')
    expect(fetchMock.mock.calls[2][1].body).toBe('{}')
    fetchMock.mock.calls.forEach(([, options]) => expect(options.headers['X-CSRF-Token']).toBe('csrf-memory'))
  })
})


function successfulFetch(payload) {
  return vi.fn().mockResolvedValue({ ok: true, status: 200, json: vi.fn().mockResolvedValue(payload) })
}
