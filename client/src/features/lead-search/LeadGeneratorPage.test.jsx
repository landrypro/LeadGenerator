import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PlaceSearchPage } from './LeadGeneratorPage'
import { leadSearchApi } from './api/leadSearchApi'

vi.mock('./api/leadSearchApi', () => ({
    leadSearchApi: {
      health: vi.fn(),
      search: vi.fn(),
      mapSnapshot: vi.fn(),
      addGoogleProspects: vi.fn(),
    },
}))


function submitSearch() {
  fireEvent.click(screen.getByRole('button', { name: /Rechercher des établissements/i }))
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
    selection_token: 'selection-token-long-enough-for-the-server',
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
    leadSearchApi.addGoogleProspects.mockResolvedValue({
      items: [{
        place_id: 'place-1',
        disposition: 'created',
        prospect: {
          id: 'prospect-1',
          internal_alias: 'Prospect Google ABC123',
          origin: 'google_place',
          source_label: 'google_places:text_search',
          google_place_id: 'place-1',
          stage_code: 'new',
          priority: 0,
          version: 1,
          created_at: '2026-08-14T12:00:00Z',
          updated_at: '2026-08-14T12:00:00Z',
          archived_at: null,
        },
      }],
    })
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
    })
    expect(payload).not.toHaveProperty('requester')
    expect(payload).not.toHaveProperty('organization_id')
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

  it('ne demande pas la carte sans la capacité google:map', async () => {
    leadSearchApi.search.mockResolvedValue(successfulResult())
    render(<PlaceSearchPage session={{ capabilities: ['google:search'] }} />)

    submitSearch()

    expect(await screen.findByText('Plomberie Boréale')).toBeInTheDocument()
    expect(leadSearchApi.mapSnapshot).not.toHaveBeenCalled()
  })

  it('demande la carte avec la capacité google:map', async () => {
    leadSearchApi.search.mockResolvedValue(successfulResult())
    render(<PlaceSearchPage session={{ capabilities: ['google:search', 'google:map'] }} />)

    submitSearch()

    await waitFor(() => expect(leadSearchApi.mapSnapshot).toHaveBeenCalledTimes(1))
  })

  it('neutralise une double soumission pendant la recherche', () => {
    leadSearchApi.search.mockReturnValue(new Promise(() => {}))
    render(<PlaceSearchPage />)

    const submit = screen.getByRole('button', { name: /Rechercher des établissements/i })
    fireEvent.click(submit)
    fireEvent.click(submit)

    expect(leadSearchApi.search).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /Recherche en cours/i })).toBeDisabled()
  })

  it('révoque l’URL blob de la carte au démontage', async () => {
    const createObjectUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:map-test')
    const revokeObjectUrl = vi.spyOn(URL, 'revokeObjectURL')
    leadSearchApi.search.mockResolvedValue(successfulResult())
    const view = render(<PlaceSearchPage session={{ capabilities: ['google:search', 'google:map'] }} />)

    submitSearch()
    await waitFor(() => expect(createObjectUrl).toHaveBeenCalledTimes(1))
    view.unmount()

    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:map-test')
    createObjectUrl.mockRestore()
    revokeObjectUrl.mockRestore()
  })

  it('annule une recherche en vol au démontage du contexte locataire', async () => {
    let capturedSignal
    leadSearchApi.search.mockImplementation((_payload, signal) => {
      capturedSignal = signal
      return new Promise(() => {})
    })
    const view = render(<PlaceSearchPage session={{ capabilities: ['google:search'] }} />)

    submitSearch()
    await waitFor(() => expect(capturedSignal).toBeInstanceOf(AbortSignal))
    view.unmount()

    expect(capturedSignal.aborted).toBe(true)
  })

  it('ajoute un établissement Google au CRM avec le jeton de sélection', async () => {
    leadSearchApi.search.mockResolvedValue(successfulResult())
    render(<PlaceSearchPage session={{ capabilities: ['google:search', 'prospects:create'] }} />)

    submitSearch()
    await screen.findByText('Plomberie Boréale')
    fireEvent.click(screen.getByRole('button', { name: /^Ajouter$/i }))

    await waitFor(() => expect(leadSearchApi.addGoogleProspects).toHaveBeenCalledTimes(1))
    expect(leadSearchApi.addGoogleProspects.mock.calls[0][0]).toEqual({
      selection_token: 'selection-token-long-enough-for-the-server',
      place_ids: ['place-1'],
    })
    expect(await screen.findByRole('button', { name: /Ajouté/i })).toBeDisabled()
  })

  it('ajoute la sélection Google au CRM sans stockage navigateur', async () => {
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem')
    leadSearchApi.search.mockResolvedValue(successfulResult())
    render(<PlaceSearchPage session={{ capabilities: ['google:search', 'prospects:create'] }} />)

    submitSearch()
    await screen.findByText('Plomberie Boréale')
    fireEvent.click(screen.getByRole('checkbox', { name: /Sélectionner Plomberie Boréale/i }))
    fireEvent.click(screen.getByRole('button', { name: /Ajouter la sélection/i }))

    await waitFor(() => expect(leadSearchApi.addGoogleProspects).toHaveBeenCalledTimes(1))
    expect(storageWrite).not.toHaveBeenCalled()
    storageWrite.mockRestore()
  })
})
