import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../shared/api/httpClient'
import { organizationApi } from './api/organizationApi'
import { OrganizationPage } from './OrganizationPage'


vi.mock('./api/organizationApi', () => ({
  organizationApi: {
    get: vi.fn(),
    update: vi.fn(),
  },
}))

const organization = {
  id: 'organization-1',
  name: 'Entreprise Exemple',
  locale: 'fr-CA',
  timezone: 'America/Toronto',
  status: 'active',
  version: 3,
  created_at: '2026-08-01T14:00:00Z',
  updated_at: '2026-08-02T15:30:00Z',
}


describe('OrganizationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    organizationApi.get.mockResolvedValue(organization)
  })

  it('affiche la fiche en lecture seule pour Manager et Sales', async () => {
    render(<OrganizationPage session={session(['organization:read'])} />)

    expect(await screen.findByRole('heading', { name: 'Organisation' })).toBeInTheDocument()
    expect(screen.getAllByText('Entreprise Exemple').length).toBeGreaterThan(0)
    expect(screen.getByText('Français (Canada)')).toBeInTheDocument()
    expect(screen.getByText('America/Toronto')).toBeInTheDocument()
    expect(screen.getAllByRole('time')).toHaveLength(2)
    expect(screen.queryByRole('heading', { name: 'Modifier l’organisation' })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('envoie seulement les champs modifiés avec la version lue', async () => {
    const updated = { ...organization, name: 'Entreprise Renommée', version: 4 }
    organizationApi.update.mockResolvedValue(updated)
    const onOrganizationUpdated = vi.fn()
    render(<OrganizationPage
      session={session(['organization:read', 'organization:update'])}
      onOrganizationUpdated={onOrganizationUpdated}
    />)
    const nameInput = await hydratedNameInput()
    const submit = screen.getByRole('button', { name: 'Enregistrer les modifications' })
    expect(submit).toBeDisabled()

    fireEvent.change(nameInput, { target: { value: 'Entreprise Renommée' } })
    await waitFor(() => expect(submit).toBeEnabled())
    fireEvent.click(submit)

    await waitFor(() => expect(organizationApi.update).toHaveBeenCalledWith(
      { version: 3, name: 'Entreprise Renommée' },
      expect.any(AbortSignal),
    ))
    expect(await screen.findByRole('status')).toHaveTextContent('ont été enregistrées')
    expect(onOrganizationUpdated).toHaveBeenCalledWith(updated)
  })

  it('propose les fuseaux IANA en auto-complétion', async () => {
    render(<OrganizationPage session={session(['organization:read', 'organization:update'])} />)

    const timezoneInput = await screen.findByRole('combobox', { name: 'Fuseau horaire IANA' })
    fireEvent.focus(timezoneInput)
    const options = Array.from(document.getElementById('organization-timezones').options).map((option) => option.value)

    expect(timezoneInput).toHaveAttribute('list', 'organization-timezones')
    expect(options).toContain('Africa/Douala')
    expect(options).toContain('America/Toronto')
    expect(options).toContain('Europe/Paris')
  })

  it('neutralise une double soumission', async () => {
    organizationApi.update.mockReturnValue(new Promise(() => {}))
    render(<OrganizationPage session={session(['organization:read', 'organization:update'])} />)
    const nameInput = await hydratedNameInput()
    fireEvent.change(nameInput, { target: { value: 'Nouveau nom' } })
    const submit = screen.getByRole('button', { name: 'Enregistrer les modifications' })
    await waitFor(() => expect(submit).toBeEnabled())

    fireEvent.click(submit)
    fireEvent.click(submit)

    await waitFor(() => expect(organizationApi.update).toHaveBeenCalledTimes(1))
    expect(await screen.findByRole('button', { name: 'Enregistrement…' })).toBeDisabled()
  })

  it('conserve la saisie sur conflit puis recharge explicitement la version actuelle', async () => {
    organizationApi.get
      .mockResolvedValueOnce(organization)
      .mockResolvedValueOnce({ ...organization, name: 'Nom du serveur', version: 4 })
    organizationApi.update.mockRejectedValue(new ApiError(
      'L’organisation a été modifiée.',
      409,
      'organization_version_conflict',
      { version: '4' },
    ))
    render(<OrganizationPage session={session(['organization:read', 'organization:update'])} />)
    const nameInput = await hydratedNameInput()
    fireEvent.change(nameInput, { target: { value: 'Ma saisie conservée' } })
    const submit = screen.getByRole('button', { name: 'Enregistrer les modifications' })
    await waitFor(() => expect(submit).toBeEnabled())
    fireEvent.click(submit)

    expect(await screen.findByRole('heading', { name: 'Une version plus récente existe' })).toBeInTheDocument()
    expect(nameInput).toHaveValue('Ma saisie conservée')
    expect(screen.getByText(/Version chargée : 3.*Version actuelle signalée : 4/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Recharger la version actuelle' }))
    await waitFor(() => expect(nameInput).toHaveValue('Nom du serveur'))
    expect(organizationApi.update).toHaveBeenCalledTimes(1)
  })

  it('annule le chargement au démontage', async () => {
    let capturedSignal
    organizationApi.get.mockImplementation((signal) => {
      capturedSignal = signal
      return new Promise(() => {})
    })
    const view = render(<OrganizationPage session={session(['organization:read'])} />)
    await waitFor(() => expect(capturedSignal).toBeInstanceOf(AbortSignal))

    view.unmount()

    expect(capturedSignal.aborted).toBe(true)
  })
})


function session(capabilities) {
  return {
    user: { id: 'user-1', display_name: 'Alex' },
    active_organization: { id: organization.id, name: organization.name },
    memberships: [],
    capabilities,
  }
}


async function hydratedNameInput() {
  const input = await screen.findByRole('textbox', { name: 'Nom' })
  await waitFor(() => expect(input).toHaveValue(organization.name))
  return input
}
