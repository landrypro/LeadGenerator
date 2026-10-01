import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DashboardPage } from './DashboardPage'
import { dashboardApi } from './api/dashboardApi'

vi.mock('./api/dashboardApi', () => ({ dashboardApi: { summary: vi.fn() } }))
vi.mock('../organizations/hooks/useMembers', () => ({
  useMembers: () => ({ items: [{ membership_id: 'member-1', status: 'disabled', user: { display_name: 'Alex', email: 'alex@example.ca' } }], nextCursor: null, error: '', loadMore: vi.fn() }),
}))

const summary = {
  period: { start_on: '2026-09-01', end_on: '2026-09-30', timezone: 'America/Toronto' },
  as_of: '2026-09-23T16:00:00Z',
  prospects_by_stage: [{ stage_code: 'new', count: 3 }],
  tasks: { due_today: 2, overdue: 1 },
  activities_by_type: [{ type: 'call', count: 4 }],
  stage_passage: [{ from_stage: 'new', to_stage: 'qualifying', cohort: 5, advanced: 2, rate_percent: '40.00', observed_until: '2026-09-23T16:00:00Z' }],
  stage_losses: [{ from_stage: 'new', cohort: 5, lost: 1 }],
  opportunities: { open: 1, won: 0, lost: 0 },
  pipeline_by_currency: [{ currency_code: 'CAD', amount: '1000.0000', weighted_amount: '500.0000' }],
  owner_breakdown: null,
  google_usage: { status: 'unavailable', used: null },
}

function session(locale = 'en-CA', capabilities = ['dashboard:read:self']) {
  return { active_organization: { id: 'org-a', locale, timezone: 'America/Toronto' }, capabilities }
}

describe('DashboardPage', () => {
  beforeEach(() => { dashboardApi.summary.mockReset(); dashboardApi.summary.mockResolvedValue(summary) })

  it('displays localized, accessible tables and unavailable Google usage', async () => {
    render(<DashboardPage session={session()} />)
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(await screen.findByRole('table', { name: 'Prospects by stage' })).toHaveTextContent('New3')
    expect(screen.getByRole('table', { name: 'Direct stage passage in the period' })).toHaveTextContent('40 %')
    expect(screen.getByText(/Metric unavailable/)).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Scope' })).not.toBeInTheDocument()
    expect(dashboardApi.summary).toHaveBeenCalledWith(expect.objectContaining({ scope: 'self', period: 'month' }), expect.any(AbortSignal))
  })

  it('lets a manager filter a disabled member and refreshes on demand', async () => {
    render(<DashboardPage session={session('fr-CA', ['dashboard:read:self', 'dashboard:read:organization'])} />)
    await screen.findByRole('heading', { name: 'Tableau de bord' })
    fireEvent.change(screen.getByRole('combobox', { name: 'Périmètre' }), { target: { value: 'owner' } })
    expect(screen.getByRole('option', { name: /désactivé/ })).toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox', { name: 'Responsable' }), { target: { value: 'member-1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Afficher' }))
    await waitFor(() => expect(dashboardApi.summary).toHaveBeenCalledWith(expect.objectContaining({ scope: 'owner', owner_membership_id: 'member-1' }), expect.any(AbortSignal)))
    const calls = dashboardApi.summary.mock.calls.length
    fireEvent.click(screen.getByRole('button', { name: 'Actualiser' }))
    await waitFor(() => expect(dashboardApi.summary.mock.calls.length).toBe(calls + 1))
  })

  it('drops an in-flight response when the page is unmounted on organization switch', async () => {
    let resolve
    dashboardApi.summary.mockReturnValue(new Promise((done) => { resolve = done }))
    const view = render(<DashboardPage session={session()} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading metrics')
    const signal = dashboardApi.summary.mock.calls[0][1]
    view.unmount()
    expect(signal.aborted).toBe(true)
    resolve(summary)
  })

  it('distinguishes a forbidden scope from loading and empty data', async () => {
    dashboardApi.summary.mockRejectedValue({ status: 403 })
    render(<DashboardPage session={session()} />)
    expect(await screen.findByText('You cannot access this scope.')).toBeInTheDocument()
    expect(screen.queryByText('No activity or progress in this period.')).not.toBeInTheDocument()
  })

  it('labels a qualified reservation counter without calling it billing', async () => {
    dashboardApi.summary.mockResolvedValue({
      ...summary,
      google_usage: { status: 'available', used: 8, unit: 'reservation', source: 'usage_quota_v1' },
    })
    render(<DashboardPage session={session()} />)
    const usage = (await screen.findByRole('heading', { name: 'Google usage' })).closest('section')
    expect(usage).toHaveTextContent('8 Text Search reservations')
    expect(usage).toHaveTextContent('reservation')
    expect(screen.queryByText(/billed/i)).not.toBeInTheDocument()
  })
})
