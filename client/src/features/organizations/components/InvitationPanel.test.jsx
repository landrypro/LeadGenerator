import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../../shared/api/httpClient'
import { organizationApi } from '../api/organizationApi'
import { InvitationPanel } from './InvitationPanel'


vi.mock('../api/organizationApi', () => ({
  organizationApi: {
    createInvitation: vi.fn(),
    resendInvitation: vi.fn(),
    revokeInvitation: vi.fn(),
  },
}))

const activeInvitation = {
  id: 'invitation-1',
  recipient_email: 'invitee@example.ca',
  role: 'sales',
  state: 'active',
  delivery_status: 'sent',
  expires_at: '2026-08-06T14:00:00Z',
  created_at: '2026-08-03T14:00:00Z',
  replayed: false,
}


describe('InvitationPanel', () => {
  beforeEach(() => vi.clearAllMocks())

  it('conserve le même UUID et le même corps après un résultat incertain', async () => {
    const createId = vi.fn().mockReturnValue('request-stable')
    organizationApi.createInvitation
      .mockRejectedValueOnce(new ApiError('Incertain.', 503, 'invitation_outcome_unknown'))
      .mockResolvedValueOnce(activeInvitation)
    const resource = invitations([])
    render(<InvitationPanel createId={createId} invitations={resource} />)

    fireEvent.change(screen.getByRole('textbox', { name: 'Adresse courriel' }), { target: { value: 'invitee@example.ca' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’invitation' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('même intention')

    fireEvent.click(screen.getByRole('button', { name: 'Créer l’invitation' }))
    await waitFor(() => expect(organizationApi.createInvitation).toHaveBeenCalledTimes(2))

    const firstPayload = organizationApi.createInvitation.mock.calls[0][0]
    const secondPayload = organizationApi.createInvitation.mock.calls[1][0]
    expect(secondPayload).toEqual(firstPayload)
    expect(firstPayload.invitation_request_id).toBe('request-stable')
    expect(createId).toHaveBeenCalledTimes(1)
    expect(resource.upsert).toHaveBeenCalledWith(activeInvitation)
  })

  it('renouvelle l’intention lorsque le formulaire change', async () => {
    const createId = vi.fn().mockReturnValueOnce('request-1').mockReturnValueOnce('request-2')
    organizationApi.createInvitation
      .mockRejectedValueOnce(new ApiError('Incertain.', 503, 'invitation_outcome_unknown'))
      .mockResolvedValueOnce(activeInvitation)
    render(<InvitationPanel createId={createId} invitations={invitations([])} />)
    const email = screen.getByRole('textbox', { name: 'Adresse courriel' })

    fireEvent.change(email, { target: { value: 'premier@example.ca' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’invitation' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    fireEvent.change(email, { target: { value: 'second@example.ca' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’invitation' }))

    await waitFor(() => expect(organizationApi.createInvitation).toHaveBeenCalledTimes(2))
    expect(organizationApi.createInvitation.mock.calls[0][0].invitation_request_id).toBe('request-1')
    expect(organizationApi.createInvitation.mock.calls[1][0].invitation_request_id).toBe('request-2')
  })

  it('neutralise une double soumission de création avant le prochain rendu', async () => {
    organizationApi.createInvitation.mockReturnValue(new Promise(() => {}))
    render(<InvitationPanel createId={() => 'request-unique'} invitations={invitations([])} />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Adresse courriel' }), { target: { value: 'invitee@example.ca' } })
    const submit = screen.getByRole('button', { name: 'Créer l’invitation' })

    fireEvent.click(submit)
    fireEvent.click(submit)

    expect(organizationApi.createInvitation).toHaveBeenCalledTimes(1)
  })

  it('conserve l’UUID d’un renvoi ambigu et remplace l’ancienne invitation au succès', async () => {
    const replacement = { ...activeInvitation, id: 'invitation-2' }
    const createId = vi.fn().mockReturnValue('resend-stable')
    organizationApi.resendInvitation
      .mockRejectedValueOnce(new ApiError('Incertain.', 503, 'invitation_outcome_unknown'))
      .mockResolvedValueOnce(replacement)
    const resource = invitations([activeInvitation])
    render(<InvitationPanel createId={createId} invitations={resource} />)

    fireEvent.click(screen.getByRole('button', { name: 'Renvoyer' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Renvoyer' }))

    await waitFor(() => expect(organizationApi.resendInvitation).toHaveBeenCalledTimes(2))
    expect(organizationApi.resendInvitation.mock.calls[0][1]).toEqual({ resend_request_id: 'resend-stable' })
    expect(organizationApi.resendInvitation.mock.calls[1][1]).toEqual({ resend_request_id: 'resend-stable' })
    expect(resource.upsert).toHaveBeenCalledWith(replacement, 'invitation-1')
  })

  it('demande confirmation avant de révoquer', async () => {
    organizationApi.revokeInvitation.mockResolvedValue({ ...activeInvitation, state: 'revoked' })
    const resource = invitations([activeInvitation])
    render(<InvitationPanel invitations={resource} />)

    fireEvent.click(screen.getByRole('button', { name: 'Révoquer' }))
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(organizationApi.revokeInvitation).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Révoquer l’invitation' }))

    await waitFor(() => expect(organizationApi.revokeInvitation).toHaveBeenCalledWith('invitation-1', expect.any(AbortSignal)))
    expect(resource.remove).toHaveBeenCalledWith('invitation-1')
  })

  it('laisse une autre invitation actionnable pendant un renvoi en cours', async () => {
    const second = { ...activeInvitation, id: 'invitation-2', recipient_email: 'second@example.ca' }
    let resolveFirst
    organizationApi.resendInvitation
      .mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve }))
      .mockResolvedValueOnce({ ...second, id: 'invitation-3' })
    render(<InvitationPanel createId={() => crypto.randomUUID()} invitations={invitations([activeInvitation, second])} />)

    const resendButtons = screen.getAllByRole('button', { name: 'Renvoyer' })
    fireEvent.click(resendButtons[0])
    await waitFor(() => expect(screen.getByRole('button', { name: 'Traitement…' })).toBeDisabled())
    const remainingResend = screen.getByRole('button', { name: 'Renvoyer' })
    expect(remainingResend).not.toBeDisabled()
    fireEvent.click(remainingResend)

    await waitFor(() => expect(organizationApi.resendInvitation).toHaveBeenCalledTimes(2))
    resolveFirst({ ...activeInvitation, id: 'invitation-4' })
  })

  it('masque toutes les mutations en lecture seule', () => {
    render(<InvitationPanel canManage={false} invitations={invitations([activeInvitation])} />)
    expect(screen.queryByRole('heading', { name: 'Inviter une personne' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Renvoyer|Révoquer/ })).not.toBeInTheDocument()
    expect(screen.getByText('invitee@example.ca')).toBeInTheDocument()
  })
})


function invitations(items) {
  return {
    items,
    nextCursor: null,
    loading: false,
    refreshing: false,
    loadingMore: false,
    error: '',
    refresh: vi.fn(),
    loadMore: vi.fn(),
    upsert: vi.fn(),
    remove: vi.fn(),
  }
}
