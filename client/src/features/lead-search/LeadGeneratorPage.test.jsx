import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { LeadGeneratorPage } from './LeadGeneratorPage'
import { leadSearchApi } from './api/leadSearchApi'

vi.mock('./api/leadSearchApi', () => ({
  leadSearchApi: {
    health: vi.fn(),
    search: vi.fn(),
    export: vi.fn(),
    mapSnapshot: vi.fn(),
  },
}))


function completeRequester() {
  fireEvent.change(screen.getByLabelText('Prénom'), { target: { value: 'Anne' } })
  fireEvent.change(screen.getByLabelText('Raison sociale'), { target: { value: 'Exemple Inc.' } })
  fireEvent.change(screen.getByLabelText('Adresse professionnelle'), {
    target: { value: '100 rue Principale, Québec' },
  })
}


describe('LeadGeneratorPage', () => {
  beforeEach(() => {
    leadSearchApi.health.mockResolvedValue({ google_api_key_configured: true })
  })

  it('ouvre l’identification et affiche le résultat soumis par le hook de recherche', async () => {
    leadSearchApi.search.mockResolvedValue({
      leads: [{
        place_id: 'place-1',
        name: 'Plomberie Boréale',
        address: 'Québec',
        phone: '',
        primary_type: 'plumber',
        business_status: 'OPERATIONAL',
        radius_verified: true,
        distance_km: 1.2,
      }],
      stats: { zones_searched: 1, api_calls: 1, duplicates_removed: 0, target_reached: false },
      generated_at: '2026-07-22T12:00:00Z',
      search_parameters: {
        query: 'plombier', radius_km: 15, target: 200, max_tiles: 8, max_pages: 3,
      },
    })
    render(<LeadGeneratorPage />)

    fireEvent.click(screen.getByRole('button', { name: /Générer les leads/i }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    completeRequester()
    fireEvent.click(screen.getByRole('button', { name: /Confirmer et générer/i }))

    await waitFor(() => expect(leadSearchApi.search).toHaveBeenCalledWith(expect.objectContaining({
      query: 'plombier',
      requester: {
        first_name: 'Anne',
        company_name: 'Exemple Inc.',
        business_address: '100 rue Principale, Québec',
      },
    })))
    expect(await screen.findByText('Plomberie Boréale')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('présente les erreurs de recherche dans la bannière commune', async () => {
    leadSearchApi.search.mockRejectedValue(new Error('Quota Google atteint.'))
    render(<LeadGeneratorPage />)

    fireEvent.click(screen.getByRole('button', { name: /Générer les leads/i }))
    completeRequester()
    fireEvent.click(screen.getByRole('button', { name: /Confirmer et générer/i }))

    expect(await screen.findByText('Quota Google atteint.')).toBeInTheDocument()
  })
})
