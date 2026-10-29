import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { platformApi } from './api/platformApi'
import { PlatformBillingPage } from './PlatformBillingPage'


vi.mock('./api/platformApi', () => ({ platformApi: {
  listBillingOrganizations: vi.fn(), getBillingOrganization: vi.fn(), listManualBillingGrantOptions: vi.fn(),
  proposeManualBillingGrant: vi.fn(), approveManualBillingGrant: vi.fn(), revokeManualBillingGrant: vi.fn(),
} }))

const item = {
  id: 'bbaea0d1-5bf4-49c1-96a6-a3c8e86e4e51', name: 'Organisation test', organization_status: 'active',
  plan_code: 'starter', version_number: 4, currency: 'XAF', subscription_state: 'active', contract_state: 'active',
  source: 'stripe', current_period_end: '2026-11-01T12:00:00Z', cancel_at_period_end: false, reconciliation_status: 'needs_review',
}

describe('PlatformBillingPage', () => {
  beforeEach(() => {
    platformApi.listBillingOrganizations.mockResolvedValue({ items: [item], next_cursor: null })
    platformApi.getBillingOrganization.mockResolvedValue({ organization: item, events: [{ event_type: 'invoice.paid', occurred_at: '2026-10-29T12:00:00Z' }], interventions: [] })
    platformApi.listManualBillingGrantOptions.mockResolvedValue([
      { plan_version_id: '4b9ca410-9891-41ea-8b24-1e23212d0d18', code: 'starter', version_number: 4, currency: 'XAF', amount_minor: 5000 },
    ])
    platformApi.proposeManualBillingGrant.mockReset().mockResolvedValue({})
    platformApi.approveManualBillingGrant.mockReset().mockResolvedValue({})
    platformApi.revokeManualBillingGrant.mockReset().mockResolvedValue({})
  })

  it('filtre et affiche une projection sans identifiant fournisseur', async () => {
    render(<PlatformBillingPage session={{ capabilities: ['platform:billing:manage'] }} />)
    expect(await screen.findByRole('button', { name: /Organisation test/ })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('État'), { target: { value: 'active' } })
    await waitFor(() => expect(platformApi.listBillingOrganizations).toHaveBeenLastCalledWith(expect.objectContaining({ state: 'active' }), expect.any(AbortSignal)))
    fireEvent.click(screen.getByRole('button', { name: /Organisation test/ }))
    expect(await screen.findByText(/invoice\.paid/)).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('cus_')
    expect(document.body.textContent).not.toContain('sub_')
  })

  it('propose une attribution sandbox sans la présenter comme un paiement', async () => {
    render(<PlatformBillingPage session={{ capabilities: ['platform:billing:manage'] }} />)
    fireEvent.click(await screen.findByRole('button', { name: /Organisation test/ }))
    const plan = await screen.findByRole('option', { name: /starter.*XAF/i })
    fireEvent.change(screen.getByLabelText('Forfait sandbox'), { target: { value: plan.value } })
    fireEvent.click(screen.getByRole('button', { name: 'Proposer l’attribution sandbox' }))

    await waitFor(() => expect(platformApi.proposeManualBillingGrant).toHaveBeenCalledWith(
      expect.objectContaining({ organization_id: item.id, plan_version_id: plan.value, duration_days: 31 }), expect.any(String),
    ))
    expect(document.body.textContent).toContain('n’est ni une facture, ni un paiement, ni un abonnement Stripe')
  })

  it('masque l’attribution lorsque le provider sandbox est désactivé', async () => {
    platformApi.listManualBillingGrantOptions.mockRejectedValueOnce({
      code: 'billing_provider_disabled', message: 'Fonctionnalité indisponible.',
    })
    render(<PlatformBillingPage session={{ capabilities: ['platform:billing:manage'] }} />)
    fireEvent.click(await screen.findByRole('button', { name: /Organisation test/ }))

    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Attribution administrative sandbox' })).not.toBeInTheDocument())
    expect(screen.queryByText('Fonctionnalité indisponible.')).not.toBeInTheDocument()
  })
})
