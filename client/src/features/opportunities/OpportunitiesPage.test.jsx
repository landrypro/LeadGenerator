import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { opportunityApi } from './api/opportunityApi'
import { OpportunitiesPage } from './OpportunitiesPage'

vi.mock('./api/opportunityApi', () => ({
  opportunityApi: { list: vi.fn() },
}))

const opportunity = {
  id: 'opportunity-1',
  prospect_id: 'prospect-1',
  name: 'OPP-17 EN',
  amount: '1250.5000',
  weighted_amount: '625.2500',
  currency_code: 'CAD',
  probability: 50,
  stage_code: 'discovery',
  expected_close_on: '2026-09-23',
  overdue: true,
}

describe('OpportunitiesPage', () => {
  beforeEach(() => {
    opportunityApi.list.mockResolvedValue({
      items: [opportunity],
      next_cursor: 'next-page',
      aggregates_by_currency: [{ currency_code: 'CAD', amount_total: '1250.5000', weighted_amount_total: '625.2500' }],
    })
  })

  it('rend le portefeuille entièrement en en-CA', async () => {
    render(<OpportunitiesPage session={{ active_organization: { locale: 'en-CA' } }} />)

    expect(await screen.findByRole('heading', { name: 'Opportunities' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Search for an opportunity or prospect')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Stage' })).toHaveDisplayValue('All stages')
    expect(screen.getByLabelText('Currency')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Overdue' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Filter' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View prospect' })).toBeInTheDocument()
    expect(screen.getAllByText('1,250.5 CAD')).toHaveLength(2)
    expect(screen.getByText('625.25 CAD')).toBeInTheDocument()
    expect(screen.getByLabelText('Totals by currency')).toHaveTextContent('625.25 CAD weighted')
    expect(screen.getAllByText('Discovery')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Load more' })).toBeInTheDocument()
    expect(screen.queryByText('Opportunités')).not.toBeInTheDocument()
    expect(screen.queryByText('Filtrer')).not.toBeInTheDocument()
    expect(screen.queryByText('Voir le prospect')).not.toBeInTheDocument()
  }, 30_000)
})
