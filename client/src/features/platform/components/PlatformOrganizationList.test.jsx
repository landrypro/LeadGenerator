import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../../shared/api/httpClient'
import { platformApi } from '../api/platformApi'
import { PlatformOrganizationList } from './PlatformOrganizationList'


vi.mock('../api/platformApi', () => ({
  platformApi: {
    reactivateOrganization: vi.fn(),
    resendInitialInvitation: vi.fn(),
    revokeInitialInvitation: vi.fn(),
    suspendOrganization: vi.fn(),
  },
}))


describe('PlatformOrganizationList', () => {
  beforeEach(() => vi.clearAllMocks())

  it('applique la matrice d’actions selon les états', () => {
    renderList([view('active'), view('expired', 'org-2'), view('revoked', 'org-3'), view('accepted', 'org-4'), view('active', 'org-5', 'active')])
    expect(screen.getAllByRole('button', { name: 'Renvoyer' })).toHaveLength(3)
    expect(screen.getAllByRole('button', { name: 'Révoquer' })).toHaveLength(2)
    expect(within(screen.getByText('org-4@example.ca').closest('li')).queryByRole('button')).not.toBeInTheDocument()
    expect(within(screen.getByText('org-5@example.ca').closest('li')).queryByRole('button')).not.toBeInTheDocument()
  })

  it('confirme la suspension et la réactivation avec une intention idempotente', async () => {
    platformApi.suspendOrganization.mockResolvedValue(view('accepted', 'org-active', 'suspended'))
    platformApi.reactivateOrganization.mockResolvedValue(view('accepted', 'org-suspended', 'active'))
    const onReconciled = vi.fn()
    renderList([view('accepted', 'org-active', 'active'), view('accepted', 'org-suspended', 'suspended')], {
      canManageStatus: true,
      onReconciled,
    })
    fireEvent.click(screen.getByRole('button', { name: 'Suspendre' }))
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Suspendre' }))
    await waitFor(() => expect(platformApi.suspendOrganization).toHaveBeenCalledTimes(1))
    expect(platformApi.suspendOrganization.mock.calls[0][1]).toMatchObject({ operation_id: 'request-id', version: 1, reason_code: 'administrative' })

    fireEvent.click(screen.getByRole('button', { name: 'Réactiver' }))
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Réactiver' }))
    await waitFor(() => expect(platformApi.reactivateOrganization).toHaveBeenCalledTimes(1))
    expect(onReconciled).toHaveBeenCalledTimes(2)
  })

  it('conserve l’identifiant d’un renvoi ambigu puis réconcilie la ligne', async () => {
    const updated = view('active')
    const createId = vi.fn().mockReturnValue('resend-stable')
    platformApi.resendInitialInvitation.mockRejectedValueOnce(new ApiError('Incertain', 503, 'provisioning_outcome_unknown')).mockResolvedValueOnce(updated)
    const onReconciled = vi.fn()
    renderList([view('active')], { createId, onReconciled })
    fireEvent.click(screen.getByRole('button', { name: 'Renvoyer' }))
    await screen.findByRole('alert')
    fireEvent.click(screen.getByRole('button', { name: 'Renvoyer' }))
    await waitFor(() => expect(platformApi.resendInitialInvitation).toHaveBeenCalledTimes(2))
    expect(platformApi.resendInitialInvitation.mock.calls.map((call) => call[1])).toEqual([{ resend_request_id: 'resend-stable' }, { resend_request_id: 'resend-stable' }])
    expect(onReconciled).toHaveBeenCalledWith(updated)
  })

  it('laisse une autre organisation actionnable pendant un renvoi en cours', () => {
    platformApi.resendInitialInvitation.mockReturnValue(new Promise(() => {}))
    renderList([view('active'), view('active', 'org-2')])
    const buttons = screen.getAllByRole('button', { name: 'Renvoyer' })
    fireEvent.click(buttons[0])
    expect(buttons[1]).toBeEnabled()
  })

  it('demande confirmation avant la révocation et réconcilie sa réponse', async () => {
    const revoked = view('revoked')
    platformApi.revokeInitialInvitation.mockResolvedValue(revoked)
    const onReconciled = vi.fn()
    renderList([view('active')], { onReconciled })
    fireEvent.click(screen.getByRole('button', { name: 'Révoquer' }))
    expect(platformApi.revokeInitialInvitation).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Révoquer l’invitation' }))
    await waitFor(() => expect(platformApi.revokeInitialInvitation).toHaveBeenCalledWith('org-1', expect.any(AbortSignal)))
    expect(onReconciled).toHaveBeenCalledWith(revoked)
  })

  it('rend le délai Retry-After et masque les mutations en lecture seule', async () => {
    platformApi.resendInitialInvitation.mockRejectedValue(new ApiError('Limite', 429, 'invitation_rate_limited', {}, '42'))
    const { rerender } = renderList([view('active')])
    fireEvent.click(screen.getByRole('button', { name: 'Renvoyer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('42 secondes')
    rerender(<PlatformOrganizationList canManage={false} organizations={resource([view('active')])} onReconciled={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /Renvoyer|Révoquer/ })).not.toBeInTheDocument()
  })
})


function renderList(items, overrides = {}) {
  return render(<PlatformOrganizationList canManage createId={() => 'request-id'} organizations={resource(items)} onReconciled={vi.fn()} {...overrides} />)
}


function resource(items) {
  return { items, loading: false, refreshing: false, loadingMore: false, error: '', nextCursor: null, refresh: vi.fn(), loadMore: vi.fn() }
}


function view(state, id = 'org-1', organizationStatus = 'provisioning') {
  return {
    organization: { id, name: `Entreprise ${id}`, locale: 'fr-CA', timezone: 'America/Toronto', status: organizationStatus, version: 1, created_at: '2026-08-03T12:00:00Z', activated_at: null },
    first_invitation: { id: `invite-${id}`, recipient_email: `${id}@example.ca`, role: 'admin', state, delivery_status: 'sent', expires_at: '2026-08-06T12:00:00Z' },
    replayed: false,
  }
}
