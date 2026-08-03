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
})
