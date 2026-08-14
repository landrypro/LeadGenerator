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

  it('envoie les mutations exactes avec CSRF', async () => {
    const fetchMock = successfulFetch({ organization: { id: 'org/1' } })
    vi.stubGlobal('fetch', fetchMock)
    configureHttpSecurity({ token: 'csrf-memory' })
    const create = { name: 'Entreprise', creation_request_id: 'create-1' }
    await platformApi.createOrganization(create)
    await platformApi.resendInitialInvitation('org/1', { resend_request_id: 'resend-1' })
    await platformApi.revokeInitialInvitation('org/1')
    await platformApi.suspendOrganization('org/1', { operation_id: 'op-1', version: 3, reason_code: 'administrative' })
    await platformApi.reactivateOrganization('org/1', { operation_id: 'op-2', version: 4, reason_code: 'customer_request' })
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/platform/organizations',
      '/api/platform/organizations/org%2F1/first-invitation/resend',
      '/api/platform/organizations/org%2F1/first-invitation/revoke',
      '/api/platform/organizations/org%2F1/suspend',
      '/api/platform/organizations/org%2F1/reactivate',
    ])
    expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify(create))
    expect(fetchMock.mock.calls[1][1].body).toBe('{"resend_request_id":"resend-1"}')
    expect(fetchMock.mock.calls[2][1].body).toBe('{}')
    expect(fetchMock.mock.calls[3][1].body).toBe('{"operation_id":"op-1","version":3,"reason_code":"administrative"}')
    expect(fetchMock.mock.calls[4][1].body).toBe('{"operation_id":"op-2","version":4,"reason_code":"customer_request"}')
    fetchMock.mock.calls.forEach(([, options]) => expect(options.headers['X-CSRF-Token']).toBe('csrf-memory'))
  })
})


function successfulFetch(payload) {
  return vi.fn().mockResolvedValue({ ok: true, status: 200, json: vi.fn().mockResolvedValue(payload) })
}
