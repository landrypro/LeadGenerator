import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { usePaginatedResource } from './usePaginatedResource'


const keyOf = (item) => item.id


function Probe({ loader }) {
  const resource = usePaginatedResource({
    loader,
    keyOf,
    fallbackMessage: 'Chargement impossible.',
  })
  return <>
    <span>{resource.items.map((item) => item.id).join(',')}</span>
    {resource.nextCursor && <button type="button" onClick={resource.loadMore}>Suite</button>}
  </>
}


describe('usePaginatedResource', () => {
  it('pagine et déduplique les ressources par identifiant', async () => {
    const loader = vi.fn()
      .mockResolvedValueOnce({ items: [{ id: 'a' }, { id: 'b' }], next_cursor: 'cursor-2' })
      .mockResolvedValueOnce({ items: [{ id: 'b' }, { id: 'c' }], next_cursor: null })
    render(<Probe loader={loader} />)

    expect(await screen.findByText('a,b')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Suite' }))

    expect(await screen.findByText('a,b,c')).toBeInTheDocument()
    expect(loader).toHaveBeenNthCalledWith(1, '', 25, expect.any(AbortSignal))
    expect(loader).toHaveBeenNthCalledWith(2, 'cursor-2', 25, expect.any(AbortSignal))
  })

  it('annule une lecture au démontage', async () => {
    let signal
    const loader = vi.fn().mockImplementation((_cursor, _limit, requestSignal) => {
      signal = requestSignal
      return new Promise(() => {})
    })
    const view = render(<Probe loader={loader} />)
    await waitFor(() => expect(signal).toBeInstanceOf(AbortSignal))

    view.unmount()

    expect(signal.aborted).toBe(true)
  })
})
