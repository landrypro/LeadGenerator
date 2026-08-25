import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { prospectApi } from './api/prospectApi'
import { ProspectsPage } from './ProspectsPage'


vi.mock('./api/prospectApi', () => ({ prospectApi: { list: vi.fn() } }))


describe('ProspectsPage', () => {
  beforeEach(() => prospectApi.list.mockResolvedValue({ items: [], next_cursor: null }))

  it('affiche une liste vide et l’action de création pour un utilisateur autorisé', async () => {
    render(<ProspectsPage session={{ capabilities: ['prospects:read', 'prospects:create'] }} />)

    expect(screen.getByRole('heading', { name: 'Prospects' })).toBeInTheDocument()
    expect(await screen.findByText('Aucun prospect à afficher')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ajouter un prospect' })).toBeInTheDocument()
  })

  it('masque l’action de création sans capacité dédiée', async () => {
    render(<ProspectsPage session={{ capabilities: ['prospects:read'] }} />)

    await screen.findByText('Aucun prospect à afficher')
    expect(screen.queryByRole('link', { name: 'Ajouter un prospect' })).not.toBeInTheDocument()
  })

  it('dissocie le nom interne du Place ID Google dans la liste', async () => {
    prospectApi.list.mockResolvedValue({
      items: [{
        id: 'prospect-1',
        internal_alias: 'Plomberie Nord',
        origin: 'google_place',
        google_place_id: 'place-google-123',
        priority: 2,
        updated_at: '2026-08-25T12:00:00Z',
        archived_at: null,
      }],
      next_cursor: null,
    })

    render(<ProspectsPage session={{ capabilities: ['prospects:read'] }} />)

    expect(await screen.findByRole('heading', { name: 'Plomberie Nord' })).toBeInTheDocument()
    expect(screen.getByText('place-google-123')).toBeInTheDocument()
    expect(screen.getByText(/Place ID/)).toBeInTheDocument()
  })
})
