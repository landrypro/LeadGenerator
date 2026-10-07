import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { axeViolations, formatViolations } from '../../test/accessibility'
import { AutomationTodayPage } from './AutomationTodayPage'
import { automationApi } from './api/automationApi'


vi.mock('./api/automationApi', () => ({ automationApi: {
  createPlan: vi.fn(),
  getToday: vi.fn(),
  getSuggestions: vi.fn(),
  recordSurfaceOpened: vi.fn(),
} }))

const session = { active_organization: { id: 'org-1', locale: 'fr-CA' } }

function readyToday() {
  automationApi.getToday.mockResolvedValue({
    counts: { open_prospects: 11, due_tasks: 2, overdue_tasks: 2, open_opportunities: 45 },
    items: [{ id: 'p-1', kind: 'prospect', label: 'Prospect Alpha', stage: 'new' }],
  })
  automationApi.getSuggestions.mockResolvedValue({
    items: [{ code: 'scope_open_prospects', label: 'Prospects ouverts', prompt: 'Montre-moi les prospects ouverts' }],
  })
}

describe('AutomationTodayPage accessibility states', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    readyToday()
  })

  it('reste sans violation axe avec le CRM réel et un plan borné', async () => {
    automationApi.createPlan.mockResolvedValue({
      result_code: 'plan_ready',
      suggestion_codes: [],
      plan: {
        resolved_count: 1,
        bounded_count: 1,
        items: [{ id: 'p-1', kind: 'prospect', label: 'Prospect Alpha', stage: 'new', priority: 2 }],
        control_codes: ['read_only'],
        not_performed_codes: ['no_crm_write'],
      },
    })
    const { container } = render(<AutomationTodayPage session={session} />)
    await screen.findByRole('heading', { name: 'Données CRM en direct' })
    const input = screen.getByRole('textbox', { name: 'Votre demande' })
    fireEvent.change(input, { target: { value: 'Montre-moi les prospects ouverts' } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Préparer un plan' })).not.toBeDisabled())
    screen.getByRole('button', { name: 'Préparer un plan' }).click()
    await screen.findByRole('heading', { name: 'Plan proposé' })

    const violations = await axeViolations(container)
    expect(formatViolations(violations)).toEqual([])
  })

  it('reste sans violation axe en état de clarification et en anglais', async () => {
    automationApi.createPlan.mockResolvedValue({ result_code: 'clarification_required', suggestion_codes: ['scope_open_prospects'], plan: null })
    const { container } = render(<AutomationTodayPage session={{ active_organization: { id: 'org-1', locale: 'en-CA' } }} />)
    await screen.findByRole('heading', { name: 'Live CRM data' })
    const input = screen.getByRole('textbox', { name: 'Your request' })
    fireEvent.change(input, { target: { value: 'Help me' } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Prepare a plan' })).not.toBeDisabled())
    screen.getByRole('button', { name: 'Prepare a plan' }).click()
    await screen.findByRole('heading', { name: 'Clarify your request' })

    const violations = await axeViolations(container)
    expect(formatViolations(violations)).toEqual([])
  })
})
