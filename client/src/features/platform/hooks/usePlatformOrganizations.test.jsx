import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { platformApi } from '../api/platformApi'
import { usePlatformOrganizations } from './usePlatformOrganizations'


vi.mock('../api/platformApi', () => ({ platformApi: { listOrganizations: vi.fn() } }))


describe('usePlatformOrganizations', () => {
  beforeEach(() => vi.clearAllMocks())

  it('charge 25 éléments, pagine et déduplique par organisation', async () => {
    platformApi.listOrganizations
      .mockResolvedValueOnce({ items: [view('org-1')], next_cursor: 'next' })
      .mockResolvedValueOnce({ items: [view('org-1'), view('org-2')], next_cursor: null })
    const { result } = renderHook(() => usePlatformOrganizations())
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(() => result.current.loadMore())
    expect(platformApi.listOrganizations.mock.calls.map((call) => call.slice(0, 2))).toEqual([['', 25], ['next', 25]])
    expect(result.current.items.map((item) => item.organization.id)).toEqual(['org-1', 'org-2'])
  })

  it('remplace une vue existante et place une nouvelle organisation en tête', async () => {
    platformApi.listOrganizations.mockResolvedValue({ items: [view('org-1')], next_cursor: null })
    const { result } = renderHook(() => usePlatformOrganizations())
    await waitFor(() => expect(result.current.loading).toBe(false))
    act(() => result.current.upsert(view('org-1', 'Mise à jour')))
    expect(result.current.items[0].organization.name).toBe('Mise à jour')
    act(() => result.current.upsert(view('org-2', 'Nouvelle')))
    expect(result.current.items.map((item) => item.organization.name)).toEqual(['Nouvelle', 'Mise à jour'])
  })
})


function view(id, name = id) {
  return { organization: { id, name }, first_invitation: { id: `invite-${id}` }, replayed: false }
}
