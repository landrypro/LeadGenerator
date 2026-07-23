import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, postJson, request } from './httpClient'


afterEach(() => vi.unstubAllGlobals())


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
      json: vi.fn().mockResolvedValue({ detail: 'Quota atteint.' }),
    }))

    await expect(request('/api/test')).rejects.toMatchObject({
      name: 'ApiError',
      message: 'Quota atteint.',
      status: 429,
    })
  })

  it('masque les erreurs réseau derrière un message contrôlé', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network details')))

    await expect(request('/api/test')).rejects.toEqual(new ApiError('Impossible de joindre le serveur.'))
  })
})
