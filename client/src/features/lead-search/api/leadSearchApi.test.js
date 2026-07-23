import { afterEach, describe, expect, it, vi } from 'vitest'

import { leadSearchApi } from './leadSearchApi'


describe('API de recherche Google', () => {
  afterEach(() => vi.restoreAllMocks())

  it('utilise exclusivement le nouveau chemin de recherche', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ places: [] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))

    await leadSearchApi.search({ query: 'plombier' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/google/places/search')
  })
})
