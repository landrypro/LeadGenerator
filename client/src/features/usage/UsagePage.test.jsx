import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { UsagePage } from './UsagePage'
import { usageApi } from './api/usageApi'

vi.mock('./api/usageApi', () => ({ usageApi: { report: vi.fn(), current: vi.fn() } }))
vi.mock('../organizations/hooks/useMembers', () => ({
  useMembers: () => ({ items: [{ membership_id: 'member-1', user: { display_name: 'Alex' } }], nextCursor: null, error: '', loadMore: vi.fn() }),
}))

const report = {
  period: { start_on: '2026-09-01', end_on: '2026-09-24', timezone: 'UTC' },
  completeness: { status: 'partial', reason: 'legacy_period' },
  google: {
    totals: [
      { code: 'google.places_text_search.quota', unit: 'reservation', accepted: 8, rejected: 1 },
      { code: 'google.places_text_search.request', unit: 'upstream_request', attempted: 8, succeeded: 7, failed: 1, indeterminate: 0 },
    ],
  },
  platform: {
    csv_export: { requested: 2, ready: 2, failed: 0, expired: 0, rows: 42, omitted: 0, bytes: 8192 },
    csv_import: { confirmed_runs: 1, examined_rows: 30, created: 25, duplicates: 2, review: 1, quarantined: 2 },
  },
  series: [{ date: '2026-09-24', operations: { 'google.places_text_search.quota:quota_reserved:accepted': 8 } }],
}
const current = {
  used: 16, remaining: 4, limit: 20, warning_threshold_percent: 80,
  reset_at: '2026-09-25T00:00:00Z', unit: 'reservation', policy_code: 'server_default_v1', source: 'redis_quota',
  enforcement_status: 'available',
}

function session(capabilities = ['usage:read:self']) {
  return { active_organization: { id: 'org-1', locale: 'fr-CA' }, capabilities }
}

describe('UsagePage', () => {
  beforeEach(() => {
    usageApi.report.mockReset(); usageApi.current.mockReset()
    usageApi.report.mockResolvedValue(report); usageApi.current.mockResolvedValue(current)
  })

  it('affiche les unités qualifiées, les volumes et l’avertissement', async () => {
    render(<UsagePage session={session()} />)
    expect(await screen.findByRole('heading', { name: 'Usage' })).toBeInTheDocument()
    expect(await screen.findByText(/16 \/ 20/)).toBeInTheDocument()
    expect(screen.getByText(/seuil d’avertissement/)).toBeInTheDocument()
    expect(screen.getByText(/ne constitue pas une facture/)).toBeInTheDocument()
    expect(screen.getByText('google.places_text_search.quota')).toBeInTheDocument()
    expect(screen.getByText(/données sont partielles/)).toBeInTheDocument()
  })

  it('autorise un gestionnaire à cibler un membre', async () => {
    render(<UsagePage session={session(['usage:read:self', 'usage:read:organization'])} />)
    await screen.findByRole('heading', { name: 'Usage' })
    fireEvent.change(screen.getByRole('combobox', { name: 'Portée' }), { target: { value: 'owner' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Membre' }), { target: { value: 'member-1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Afficher' }))
    await waitFor(() => expect(usageApi.report).toHaveBeenLastCalledWith(
      expect.objectContaining({ scope: 'owner', owner_membership_id: 'member-1' }), expect.any(AbortSignal),
    ))
  })
})
