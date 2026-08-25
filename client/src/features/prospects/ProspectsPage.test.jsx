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
})
