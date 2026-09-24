import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PlaceSearchPage } from './LeadGeneratorPage'
import { leadSearchApi } from './api/leadSearchApi'

vi.mock('./api/leadSearchApi', () => ({
    leadSearchApi: {
      health: vi.fn(),
      suggestLocation: vi.fn(),
      resolveLocation: vi.fn(),
      search: vi.fn(),
      mapSnapshot: vi.fn(),
      addGoogleProspects: vi.fn(),
    },
}))


function submitSearch() {
  fireEvent.click(screen.getByRole('button', { name: /Coordonnées avancées/i }))
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
          internal_alias: 'Plomberie Nord',
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

  it('résout un pays puis une ville avant de chercher, sans requête sur une simple saisie', async () => {
    leadSearchApi.suggestLocation.mockImplementation(async ({ scope }) => ({ items: [{
      label: scope === 'area' ? 'Canada' : 'Montréal, Québec, Canada',
      selection_token: scope === 'area' ? 'area-token' : 'city-token',
    }] }))
    leadSearchApi.resolveLocation.mockImplementation(async ({ selection_token }) => ({
      label: selection_token === 'area-token' ? 'Canada' : 'Montréal, Québec, Canada',
      scope: selection_token === 'area-token' ? 'area' : 'locality',
      latitude: 45.5017, longitude: -73.5673, region_code: 'CA',
    }))
    leadSearchApi.search.mockResolvedValue(successfulResult())
    render(<PlaceSearchPage />)

    fireEvent.change(screen.getByRole('combobox', { name: 'Pays ou région' }), { target: { value: 'Cana' } })
    expect(screen.getByRole('button', { name: /Rechercher des établissements/i })).toBeDisabled()
    expect(leadSearchApi.search).not.toHaveBeenCalled()
    fireEvent.click(await screen.findByRole('option', { name: 'Canada' }))
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Pays ou région' })).toHaveValue('Canada'))

    fireEvent.change(screen.getByRole('combobox', { name: 'Ville ou quartier' }), { target: { value: 'Montr' } })
    fireEvent.click(await screen.findByRole('option', { name: /Montréal/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Rechercher des établissements/i })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: /Rechercher des établissements/i }))
    await waitFor(() => expect(leadSearchApi.search).toHaveBeenCalledWith(expect.objectContaining({
      center_latitude: 45.5017, center_longitude: -73.5673, region_code: 'CA',
    }), expect.any(AbortSignal)))
  })

  it('ne sollicite pas Google pour moins de trois caractères et indique une absence de proposition', async () => {
    leadSearchApi.suggestLocation.mockResolvedValue({ items: [] })
    render(<PlaceSearchPage />)
    const area = screen.getByRole('combobox', { name: 'Pays ou région' })
    fireEvent.change(area, { target: { value: 'Ca' } })
    expect(leadSearchApi.suggestLocation).not.toHaveBeenCalled()
    fireEvent.change(area, { target: { value: 'Cana' } })
    expect(await screen.findByText('Aucun lieu correspondant. Précisez votre saisie.')).toBeInTheDocument()
    expect(leadSearchApi.suggestLocation).toHaveBeenCalledTimes(1)
    expect(leadSearchApi.search).not.toHaveBeenCalled()
  })

  it('utilise en-CA pour les libellés et la recherche', async () => {
    leadSearchApi.search.mockResolvedValue(successfulResult())
    render(<PlaceSearchPage session={{ active_organization: { locale: 'en-CA' } }} />)
    expect(screen.getByRole('combobox', { name: 'Country or region' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'City or neighbourhood' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Advanced coordinates/i }))
    fireEvent.click(screen.getByRole('button', { name: /Search businesses/i }))
    await waitFor(() => expect(leadSearchApi.search).toHaveBeenCalledWith(expect.objectContaining({
      language_code: 'en',
    }), expect.any(AbortSignal)))
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

    fireEvent.click(screen.getByRole('button', { name: /Coordonnées avancées/i }))
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
    fireEvent.change(screen.getByLabelText('Nom interne CRM pour Plomberie Boréale'), { target: { value: 'Plomberie Nord' } })
    const addButton = screen.getByRole('button', { name: /^Ajouter$/i })
    await waitFor(() => expect(addButton).toBeEnabled())
    fireEvent.click(addButton)

    await waitFor(() => expect(leadSearchApi.addGoogleProspects).toHaveBeenCalledTimes(1))
    expect(leadSearchApi.addGoogleProspects.mock.calls[0][0]).toEqual({
      selection_token: 'selection-token-long-enough-for-the-server',
      items: [{ place_id: 'place-1', internal_alias: 'Plomberie Nord' }],
    })
    expect(await screen.findByRole('button', { name: /Ajouté/i })).toBeDisabled()
  })

  it('ajoute la sélection Google au CRM sans stockage navigateur', async () => {
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem')
    leadSearchApi.search.mockResolvedValue(successfulResult())
    render(<PlaceSearchPage session={{ capabilities: ['google:search', 'prospects:create'] }} />)

    submitSearch()
    await screen.findByText('Plomberie Boréale')
    fireEvent.change(screen.getByLabelText('Nom interne CRM pour Plomberie Boréale'), { target: { value: 'Plomberie Nord' } })
    fireEvent.click(screen.getByRole('checkbox', { name: /Sélectionner Plomberie Boréale/i }))
    const addSelectionButton = screen.getByRole('button', { name: /Ajouter la sélection/i })
    await waitFor(() => expect(addSelectionButton).toBeEnabled())
    fireEvent.click(addSelectionButton)

    await waitFor(() => expect(leadSearchApi.addGoogleProspects).toHaveBeenCalledTimes(1))
    expect(storageWrite).not.toHaveBeenCalled()
    storageWrite.mockRestore()
  })

  it('affiche le Place ID séparément et exige un nom interne CRM', async () => {
    leadSearchApi.search.mockResolvedValue(successfulResult())
    render(<PlaceSearchPage session={{ capabilities: ['google:search', 'prospects:create'] }} />)

    submitSearch()

    expect(await screen.findByText('place-1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Ajouter$/i })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Nom interne CRM pour Plomberie Boréale'), { target: { value: 'Compte Québec' } })
    expect(screen.getByRole('button', { name: /^Ajouter$/i })).toBeEnabled()
  })
})
