import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AutomationTodayPage } from './AutomationTodayPage'
import { automationApi } from './api/automationApi'


vi.mock('./api/automationApi', () => ({ automationApi: { createPlan: vi.fn() } }))

const session = { active_organization: { id: 'org-1', locale: 'fr-CA' } }

describe('AutomationTodayPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('prépare un plan éphémère sans second appel quand il est confirmé localement', async () => {
    automationApi.createPlan.mockResolvedValue({
      result_code: 'plan_ready', suggestion_codes: [],
      plan: {
        resolved_count: 75, bounded_count: 50,
        control_codes: ['read_only'], not_performed_codes: ['no_crm_write', 'no_job'],
      },
    })
    render(<AutomationTodayPage session={session} />)

    fireEvent.change(screen.getByLabelText('Votre demande'), { target: { value: 'Montre mes prospects ouverts' } })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer un plan' }))

    expect(await screen.findByRole('heading', { name: 'Plan proposé' })).toBeInTheDocument()
    expect(automationApi.createPlan).toHaveBeenCalledWith({
      input_mode: 'free_text', user_text: 'Montre mes prospects ouverts', suggestion_code: null,
    })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer ce plan' }))
    expect(screen.getByRole('status')).toHaveTextContent('Aucune donnée ni tâche n’a été créée')
    expect(automationApi.createPlan).toHaveBeenCalledTimes(1)
  })

  it('bascule sur les suggestions guidées lors du repli', async () => {
    automationApi.createPlan.mockResolvedValue({
      result_code: 'fallback_guided', suggestion_codes: ['scope_open_prospects'], plan: null,
    })
    render(<AutomationTodayPage session={session} />)
    fireEvent.change(screen.getByLabelText('Votre demande'), { target: { value: 'Aide-moi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer un plan' }))
    expect(await screen.findByText(/mode libre est temporairement indisponible/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cadrer mes prospects ouverts' }))
    await waitFor(() => expect(automationApi.createPlan).toHaveBeenLastCalledWith({
      input_mode: 'guided', user_text: null, suggestion_code: 'scope_open_prospects',
    }))
  })

  it('affiche le message quand la préparation est refusée par le backend', async () => {
    automationApi.createPlan.mockRejectedValue(new Error('L’assistant est désactivé.'))
    render(<AutomationTodayPage session={session} />)

    fireEvent.change(screen.getByLabelText('Votre demande'), { target: { value: 'Montre mes prospects ouverts' } })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer un plan' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('L’assistant est désactivé.')
  })
})
