import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, configureHttpSecurity, postJson, request } from './httpClient'


afterEach(() => {
  configureHttpSecurity()
  vi.unstubAllGlobals()
})


describe('httpClient', () => {
  it('décode une réponse JSON et transmet le corps demandé', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ status: 'ok' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(postJson('/api/test', { query: 'plombier' })).resolves.toEqual({ status: 'ok' })
    expect(fetchMock).toHaveBeenCalledWith('/api/test', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ query: 'plombier' }),
    }))
  })

  it('convertit les erreurs HTTP en erreur utilisateur stable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: vi.fn().mockResolvedValue({
        error: { code: 'quota_reached', message: 'Quota atteint.', fields: { limit: '20' } },
      }),
    }))

    await expect(request('/api/test')).rejects.toMatchObject({
      name: 'ApiError',
      message: 'Quota atteint.',
      status: 429,
      code: 'quota_reached',
      fields: { limit: '20' },
    })
  })

  it('masque les erreurs réseau derrière un message contrôlé', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network details')))

    await expect(request('/api/test')).rejects.toEqual(new ApiError('Impossible de joindre le serveur.'))
  })

  it('joint le cookie et le jeton CSRF en mémoire aux mutations', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    })
    vi.stubGlobal('fetch', fetchMock)
    configureHttpSecurity({ token: 'csrf-en-memoire' })

    await postJson('/api/auth/logout', {})

    expect(fetchMock).toHaveBeenCalledWith('/api/auth/logout', expect.objectContaining({
      credentials: 'same-origin',
      headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-en-memoire' }),
    }))
  })

  it('signale centralement la perte de session après un 401', async () => {
    const onUnauthorized = vi.fn()
    configureHttpSecurity({ onUnauthorized })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({ error: { message: 'Authentification requise.' } }),
    }))

    await expect(request('/api/auth/me')).rejects.toMatchObject({ status: 401 })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })
})
