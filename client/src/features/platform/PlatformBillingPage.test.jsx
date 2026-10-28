import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { platformApi } from './api/platformApi'
import { PlatformBillingPage } from './PlatformBillingPage'


vi.mock('./api/platformApi', () => ({ platformApi: { listBillingOrganizations: vi.fn(), getBillingOrganization: vi.fn() } }))

const item = {
  id: 'bbaea0d1-5bf4-49c1-96a6-a3c8e86e4e51', name: 'Organisation test', organization_status: 'active',
  plan_code: 'starter', version_number: 4, currency: 'XAF', subscription_state: 'active', contract_state: 'active',
  source: 'stripe', current_period_end: '2026-11-01T12:00:00Z', cancel_at_period_end: false, reconciliation_status: 'needs_review',
}

describe('PlatformBillingPage', () => {
  beforeEach(() => {
    platformApi.listBillingOrganizations.mockResolvedValue({ items: [item], next_cursor: null })
    platformApi.getBillingOrganization.mockResolvedValue({ organization: item, events: [{ event_type: 'invoice.paid', occurred_at: '2026-10-29T12:00:00Z' }], interventions: [] })
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
})
