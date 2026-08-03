import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../../shared/api/httpClient'
import { platformApi } from '../api/platformApi'
import { ProvisionOrganizationForm } from './ProvisionOrganizationForm'


vi.mock('../api/platformApi', () => ({ platformApi: { createOrganization: vi.fn() } }))


describe('ProvisionOrganizationForm', () => {
  beforeEach(() => vi.clearAllMocks())

  it('normalise le corps et conserve la même intention après un résultat incertain', async () => {
    const createId = vi.fn().mockReturnValue('stable-id')
    platformApi.createOrganization.mockRejectedValueOnce(new ApiError('Incertain', 503, 'provisioning_outcome_unknown')).mockResolvedValueOnce(view())
    const onProvisioned = vi.fn()
    render(<ProvisionOrganizationForm createId={createId} onProvisioned={onProvisioned} />)
    fill('  Entreprise   Démo  ', 'admin@example.ca')
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’organisation' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('même intention')
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer la même intention' }))
    await waitFor(() => expect(platformApi.createOrganization).toHaveBeenCalledTimes(2))
    expect(platformApi.createOrganization.mock.calls[0][0]).toEqual(platformApi.createOrganization.mock.calls[1][0])
    expect(platformApi.createOrganization.mock.calls[0][0]).toEqual(expect.objectContaining({ name: 'Entreprise Démo', first_administrator_email: 'admin@example.ca', creation_request_id: 'stable-id' }))
    expect(createId).toHaveBeenCalledTimes(1)
    expect(onProvisioned).toHaveBeenCalledWith(view())
  })

  it('renouvelle l’intention après une modification', async () => {
    const createId = vi.fn().mockReturnValueOnce('id-1').mockReturnValueOnce('id-2')
    platformApi.createOrganization.mockRejectedValueOnce(new ApiError('Incertain', 503, 'provisioning_outcome_unknown')).mockResolvedValueOnce(view())
    render(<ProvisionOrganizationForm createId={createId} onProvisioned={vi.fn()} />)
    fill('Première', 'admin@example.ca')
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’organisation' }))
    await screen.findByRole('alert')
    fireEvent.change(screen.getByRole('textbox', { name: 'Nom de l’organisation' }), { target: { value: 'Deuxième' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’organisation' }))
    await waitFor(() => expect(platformApi.createOrganization).toHaveBeenCalledTimes(2))
    expect(platformApi.createOrganization.mock.calls.map(([payload]) => payload.creation_request_id)).toEqual(['id-1', 'id-2'])
  })

  it('bloque une clé réutilisée jusqu’à l’abandon explicite', async () => {
    const createId = vi.fn().mockReturnValueOnce('bad-id').mockReturnValueOnce('new-id')
    platformApi.createOrganization.mockRejectedValueOnce(new ApiError('Conflit', 409, 'idempotency_key_reused')).mockResolvedValueOnce(view())
    render(<ProvisionOrganizationForm createId={createId} onProvisioned={vi.fn()} />)
    fill('Entreprise', 'admin@example.ca')
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’organisation' }))
    const abandon = await screen.findByRole('button', { name: 'Abandonner cette intention' })
    expect(screen.getByRole('button', { name: 'Réessayer la même intention' })).toBeDisabled()
    fireEvent.click(abandon)
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’organisation' }))
    await waitFor(() => expect(platformApi.createOrganization).toHaveBeenCalledTimes(2))
    expect(platformApi.createOrganization.mock.calls[1][0].creation_request_id).toBe('new-id')
  })

  it('neutralise un double clic synchrone et signale une livraison échouée sans annuler la création', async () => {
    let resolve
    platformApi.createOrganization.mockReturnValue(new Promise((done) => { resolve = done }))
    render(<ProvisionOrganizationForm createId={() => 'one'} onProvisioned={vi.fn()} />)
    fill('Entreprise', 'admin@example.ca')
    const button = screen.getByRole('button', { name: 'Créer l’organisation' })
    fireEvent.click(button); fireEvent.click(button)
    expect(platformApi.createOrganization).toHaveBeenCalledTimes(1)
    resolve(view({ delivery_status: 'failed' }))
    expect(await screen.findByRole('status')).toHaveTextContent('organisation a été créée')
  })
})


function fill(name, email) {
  fireEvent.change(screen.getByRole('textbox', { name: 'Nom de l’organisation' }), { target: { value: name } })
  fireEvent.change(screen.getByRole('textbox', { name: 'Courriel de l’administrateur initial' }), { target: { value: email } })
}


function view(invitation = {}) {
  return { organization: { id: 'org-1', name: 'Entreprise', status: 'provisioning' }, first_invitation: { id: 'invite-1', delivery_status: 'sent', ...invitation }, replayed: false }
}
