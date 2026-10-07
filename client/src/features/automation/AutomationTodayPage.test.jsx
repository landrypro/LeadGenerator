import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AutomationTodayPage } from './AutomationTodayPage'
import { automationApi } from './api/automationApi'


vi.mock('./api/automationApi', () => ({ automationApi: { createPlan: vi.fn(), getToday: vi.fn(), getSuggestions: vi.fn() } }))

const session = { active_organization: { id: 'org-1', locale: 'fr-CA' } }

describe('AutomationTodayPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    automationApi.getToday.mockResolvedValue({
      counts: { open_prospects: 2, due_tasks: 1, overdue_tasks: 0, open_opportunities: 1 },
      items: [],
    })
    automationApi.getSuggestions.mockResolvedValue({
      items: [
        { code: 'scope_open_prospects', label: 'Prospects ouverts', prompt: 'Montre-moi les prospects ouverts' },
        { code: 'rebalance_open_prospects', label: 'Rééquilibrer la charge', prompt: 'Répartis les prospects en cours entre mon équipe' },
        { code: 'prepare_new_prospect_followup', label: 'Nouveaux prospects à suivre', prompt: 'Prépare le suivi des nouveaux prospects' },
      ],
    })
  })

  it('prépare un plan éphémère sans second appel quand il est confirmé localement', async () => {
    automationApi.createPlan.mockResolvedValue({
      result_code: 'plan_ready', suggestion_codes: [],
      intent: { scope_kind: 'assigned_open_prospects' },
      plan: {
        resolved_count: 75, bounded_count: 50,
        control_codes: ['read_only'], not_performed_codes: ['no_crm_write', 'no_job'],
      },
    })
    render(<AutomationTodayPage session={session} />)

    fireEvent.change(screen.getByLabelText('Votre demande'), { target: { value: 'Montre mes prospects ouverts' } })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer un plan' }))

    expect(await screen.findByRole('heading', { name: 'Plan proposé' })).toBeInTheDocument()
    expect(screen.getByText(/Périmètre examiné : prospects ouverts qui vous sont attribués/)).toBeInTheDocument()
    expect(automationApi.createPlan).toHaveBeenCalledWith({
      input_mode: 'free_text', user_text: 'Montre mes prospects ouverts', suggestion_code: null,
    })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer ce plan' }))
    expect(screen.getByText(/Aucune donnée ni tâche n’a été créée/)).toBeInTheDocument()
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

  it('explique l’indisponibilité sans exposer de commande Assistant', async () => {
    render(<AutomationTodayPage session={{ ...session, automation_assistant_available: false }} />)

    expect(await screen.findByRole('heading', { name: 'Préparation de plans indisponible' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Votre demande')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Préparer un plan' })).not.toBeInTheDocument()
    expect(automationApi.getSuggestions).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: 'Données CRM en direct' })).toBeInTheDocument()
  })

  it('charge les suggestions et permet une sélection clavier sans soumettre', async () => {
    render(<AutomationTodayPage session={session} />)
    const input = screen.getByRole('textbox', { name: 'Votre demande' })

    fireEvent.change(input, { target: { value: 'p' } })
    expect(await screen.findByRole('listbox', { name: 'Suggestions guidées' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Prospects ouverts/ })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'ArrowUp' })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(input).toHaveValue('Montre-moi les prospects ouverts')
    expect(automationApi.createPlan).not.toHaveBeenCalled()
    expect(input).not.toHaveAttribute('aria-expanded')

    fireEvent.change(input, { target: { value: 'prospects' } })
    expect(await screen.findByRole('listbox', { name: 'Suggestions guidées' })).toBeInTheDocument()
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(input).not.toHaveAttribute('aria-expanded')
  })

  it('affiche la projection CRM bornée reçue du backend', async () => {
    automationApi.getToday.mockResolvedValue({
      counts: { open_prospects: 4, due_tasks: 2, overdue_tasks: 1, open_opportunities: 3 },
      items: [{ id: 'p-1', kind: 'prospect', label: 'Atelier Alpha', stage: 'new' }],
    })
    render(<AutomationTodayPage session={session} />)

    expect(await screen.findByRole('heading', { name: 'Données CRM en direct' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Données CRM en direct' })).toHaveTextContent('Atelier Alpha')
    expect(screen.getByText('Prospects ouverts').nextElementSibling).toHaveTextContent('4')
  })

  it('affiche les éléments CRM du plan et leur état borné', async () => {
    automationApi.createPlan.mockResolvedValue({
      result_code: 'plan_ready', suggestion_codes: [],
      plan: {
        resolved_count: 1, bounded_count: 1,
        items: [{ id: 'p-1', kind: 'prospect', label: 'Atelier Alpha', stage: 'new', priority: 2 }],
        control_codes: ['read_only'], not_performed_codes: ['no_crm_write'],
      },
    })
    render(<AutomationTodayPage session={session} />)
    fireEvent.change(screen.getByLabelText('Votre demande'), { target: { value: 'Montre mes prospects ouverts' } })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer un plan' }))

    expect(await screen.findByRole('heading', { name: 'Éléments CRM du plan' })).toBeInTheDocument()
    expect(screen.getByText(/Atelier Alpha/)).toBeInTheDocument()
  })

  it('affiche un état explicite quand le plan ne trouve aucun élément', async () => {
    automationApi.createPlan.mockResolvedValue({
      result_code: 'plan_ready', suggestion_codes: [],
      plan: { resolved_count: 0, bounded_count: 0, items: [], control_codes: [], not_performed_codes: [] },
    })
    render(<AutomationTodayPage session={session} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cadrer mes prospects ouverts' }))

    expect(await screen.findByRole('heading', { name: 'Aucun élément CRM trouvé' })).toBeInTheDocument()
    expect(screen.getByText(/Le périmètre autorisé ne contient aucun élément/)).toBeInTheDocument()
  })

  it('explique la clarification et propose une prochaine étape', async () => {
    automationApi.createPlan.mockResolvedValue({ result_code: 'clarification_required', suggestion_codes: ['scope_open_prospects'], plan: null })
    render(<AutomationTodayPage session={session} />)
    fireEvent.change(screen.getByLabelText('Votre demande'), { target: { value: 'Aide-moi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer un plan' }))

    expect(await screen.findByRole('heading', { name: 'Précisez votre demande' })).toBeInTheDocument()
    expect(screen.getByText(/Essayez une formulation proposée/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cadrer mes prospects ouverts' })).toBeInTheDocument()
  })

  it('affiche le refus explicite et le repli guidé', async () => {
    automationApi.createPlan.mockResolvedValueOnce({ result_code: 'intent_not_supported', suggestion_codes: [], plan: null })
    render(<AutomationTodayPage session={session} />)
    fireEvent.change(screen.getByLabelText('Votre demande'), { target: { value: 'Supprime mes prospects' } })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer un plan' }))
    expect(await screen.findByRole('heading', { name: 'Cette demande n’est pas prise en charge dans IMP-A5.' })).toBeInTheDocument()
    expect(screen.getByText(/Aucune action n’a été exécutée/)).toBeInTheDocument()

    automationApi.createPlan.mockResolvedValueOnce({ result_code: 'fallback_guided', suggestion_codes: ['scope_open_prospects'], plan: null })
    fireEvent.change(screen.getByLabelText('Votre demande'), { target: { value: 'Une demande libre' } })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer un plan' }))
    expect(await screen.findByRole('heading', { name: 'Le mode libre est temporairement indisponible. Utilisez une suggestion guidée.' })).toBeInTheDocument()
    expect(screen.getByText(/Le mode libre n’a pas pu être interprété/)).toBeInTheDocument()
  })

  it('permet de relancer une préparation après une erreur API', async () => {
    automationApi.createPlan
      .mockRejectedValueOnce(new Error('Service indisponible.'))
      .mockResolvedValueOnce({ result_code: 'clarification_required', suggestion_codes: [], plan: null })
    render(<AutomationTodayPage session={session} />)
    fireEvent.change(screen.getByLabelText('Votre demande'), { target: { value: 'Montre mes prospects ouverts' } })
    fireEvent.click(screen.getByRole('button', { name: 'Préparer un plan' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Service indisponible.')
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByRole('heading', { name: 'Précisez votre demande' })).toBeInTheDocument()
  })

  it('permet de relancer le chargement des données CRM après une erreur réseau', async () => {
    automationApi.getToday
      .mockRejectedValueOnce(new Error('CRM indisponible.'))
      .mockResolvedValueOnce({ counts: { open_prospects: 9 }, items: [] })
    render(<AutomationTodayPage session={session} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('CRM indisponible.')
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(screen.getByText('Prospects ouverts').nextElementSibling).toHaveTextContent('9'))
  })

  it('présente les états non supportés en anglais canadien', async () => {
    automationApi.createPlan.mockResolvedValue({ result_code: 'intent_not_supported', suggestion_codes: [], plan: null })
    render(<AutomationTodayPage session={{ active_organization: { id: 'org-1', locale: 'en-CA' } }} />)
    fireEvent.change(screen.getByLabelText('Your request'), { target: { value: 'Delete my prospects' } })
    fireEvent.click(screen.getByRole('button', { name: 'Prepare a plan' }))

    expect(await screen.findByRole('heading', { name: 'This request is not supported in IMP-A5.' })).toBeInTheDocument()
    expect(screen.getByText(/No action was executed/)).toBeInTheDocument()
  })
})
