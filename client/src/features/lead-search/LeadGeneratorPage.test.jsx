import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PlaceSearchPage } from './LeadGeneratorPage'
import { leadSearchApi } from './api/leadSearchApi'

vi.mock('./api/leadSearchApi', () => ({
  leadSearchApi: {
    health: vi.fn(),
    search: vi.fn(),
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


function submitSearch() {
  fireEvent.click(screen.getByRole('button', { name: /Rechercher des établissements/i }))
  completeRequester()
  fireEvent.click(screen.getByRole('button', { name: /Confirmer la recherche/i }))
}


function successfulResult() {
  return {
    places: [{
      place_id: 'place-1',
      name: 'Plomberie Boréale',
      address: 'Québec',
      primary_type: 'plumber',
      business_status: 'OPERATIONAL',
      radius_verified: true,
      distance_km: 1.2,
    }],
    stats: { api_calls: 1, raw_results: 1, displayed_results: 1 },
    searched_at: '2026-07-22T12:00:00Z',
    map_snapshot_token: 'snapshot-token-long-enough-for-the-server',
    search_parameters: {
      query: 'plombier',
      center_latitude: 46.8139,
      center_longitude: -71.208,
      radius_km: 15,
      include_service_area_businesses: true,
      language_code: 'fr',
      region_code: 'CA',
    },
  }
}


describe('PlaceSearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    leadSearchApi.health.mockResolvedValue({ google_api_key_configured: true })
    leadSearchApi.mapSnapshot.mockResolvedValue(new Blob(['map'], { type: 'image/png' }))
  })

  it('soumet uniquement les paramètres de la recherche limitée et affiche le résultat', async () => {
    leadSearchApi.search.mockResolvedValue(successfulResult())
    render(<PlaceSearchPage />)

    submitSearch()

    await waitFor(() => expect(leadSearchApi.search).toHaveBeenCalledTimes(1))
    const payload = leadSearchApi.search.mock.calls[0][0]
    expect(payload).toMatchObject({
      query: 'plombier',
      radius_km: 15,
      requester: {
        first_name: 'Anne',
        company_name: 'Exemple Inc.',
        business_address: '100 rue Principale, Québec',
      },
    })
    expect(payload).not.toHaveProperty('target')
    expect(payload).not.toHaveProperty('max_tiles')
    expect(payload).not.toHaveProperty('max_pages')
    expect(payload).not.toHaveProperty('contact_fields')
    expect(await screen.findByText('Plomberie Boréale')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('garde l’export inaccessible et affiche l’attribution Google Maps', () => {
    render(<PlaceSearchPage />)

    expect(screen.getByRole('button', { name: /Exporter Excel/i })).toBeDisabled()
    expect(screen.getByLabelText('Attribution Google Maps')).toHaveTextContent('Google Maps')
    expect(screen.getByLabelText('Attribution Google Maps')).toHaveAttribute('translate', 'no')
    expect(screen.queryByText(/générateur|leads/i)).not.toBeInTheDocument()
  })

  it('ne stocke pas les résultats dans le stockage navigateur', async () => {
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem')
    leadSearchApi.search.mockResolvedValue(successfulResult())
    render(<PlaceSearchPage />)

    submitSearch()

    expect(await screen.findByText('Plomberie Boréale')).toBeInTheDocument()
    expect(storageWrite).not.toHaveBeenCalled()
    storageWrite.mockRestore()
  })

  it('présente les erreurs de recherche dans la bannière commune', async () => {
    leadSearchApi.search.mockRejectedValue(new Error('Quota Google atteint.'))
    render(<PlaceSearchPage />)

    submitSearch()

    expect(await screen.findByText('Quota Google atteint.')).toBeInTheDocument()
  })
})
