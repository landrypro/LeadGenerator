import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AutomationExceptionsPage } from './AutomationExceptionsPage'
import { AutomationPlaybooksPage } from './AutomationPlaybooksPage'
import { AutomationWorkspace } from './AutomationWorkspace'

vi.mock('./api/automationApi', () => ({
  automationApi: { listPlaybooks: vi.fn(), listExceptions: vi.fn(), runPreflight: vi.fn(), transitionPlaybook: vi.fn(), transitionException: vi.fn() },
}))

import { automationApi } from './api/automationApi'


const session = { active_organization: { id: 'org-1', locale: 'fr-CA' } }

describe('coque Automatisation et états honnêtes', () => {
  beforeEach(() => {
    automationApi.listPlaybooks.mockResolvedValue({ items: [] })
    automationApi.listExceptions.mockResolvedValue({ items: [] })
    automationApi.runPreflight.mockResolvedValue({ item: { state: 'completed', expires_at: '2026-10-05T12:15:00Z' } })
    automationApi.transitionPlaybook.mockResolvedValue({ item: { state: 'suspended', version: 4, prepare_enabled: false } })
    automationApi.transitionException.mockResolvedValue({ item: { state: 'in_progress', version: 2 } })
  })

  it('présente les trois Playbooks sans simuler une activation', async () => {
    render(<AutomationPlaybooksPage session={session} />)

    expect(await screen.findByRole('heading', { name: 'Playbooks' })).toBeInTheDocument()
    expect(screen.getAllByText('Prévol et activation non disponibles')).toHaveLength(3)
    expect(screen.queryByRole('button', { name: /Activer|Suspendre|Prévol/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Aucun envoi externe/i)).toBeInTheDocument()
  })

  it('affiche les volumes CRM sans créer de configuration Playbook', async () => {
    automationApi.listPlaybooks.mockResolvedValue({
      items: [],
      live_scopes: {
        new_prospect: { subject_count: 3 },
        proposal_pending: { subject_count: 1 },
        forgotten_opportunity: { subject_count: 0 },
      },
    })
    render(<AutomationPlaybooksPage session={session} />)

    expect(await screen.findAllByText(/Objets CRM correspondants/)).toHaveLength(3)
    expect(screen.getByText('Objets CRM correspondants : 3')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Activer|Suspendre|Prévol/ })).not.toBeInTheDocument()
  })

  it('distingue un état vide d’une promesse de traitement automatique', async () => {
    render(<AutomationExceptionsPage session={session} />)

    expect(await screen.findByRole('heading', { name: 'Aucune entrée ou exception à traiter' })).toBeInTheDocument()
    expect(screen.getByText(/aucun traitement automatique n’est en attente/i)).toBeInTheDocument()
    expect(screen.getByText('Ouverte')).toBeInTheDocument()
    expect(screen.getByText('À vérifier')).toBeInTheDocument()
  })

  it('demande une confirmation avant de prendre une exception en charge', async () => {
    automationApi.listExceptions.mockResolvedValue({
      items: [{ id: 'exception-1', exception_code: 'owner_unavailable', state: 'open', version: 1 }],
    })
    render(<AutomationExceptionsPage session={{ ...session, capabilities: ['automation:exceptions:resolve:self'] }} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Prendre en charge' }))
    expect(screen.getByText(/Confirmez cette décision humaine/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(automationApi.transitionException).toHaveBeenCalledWith(
      'exception-1', 'claim', 1, expect.any(String), { resolutionCode: undefined },
    )
    expect(await screen.findByText(/Exception mise à jour sans effet CRM/i)).toBeInTheDocument()
  })

  it('affiche une projection lue sans proposer de commande métier', async () => {
    automationApi.listPlaybooks.mockResolvedValue({
      items: [{ code: 'new_prospect', state: 'preflight_required', latest_preflight_state: 'valid' }],
    })
    automationApi.listExceptions.mockResolvedValue({
      items: [{ id: 'exception-1', exception_code: 'owner_unavailable', subject_label: 'Atelier Alpha', subject_stage: 'new', state: 'open' }],
    })

    const { unmount } = render(<AutomationPlaybooksPage session={session} />)
    expect(await screen.findByText('Prévol requis')).toBeInTheDocument()
    expect(screen.getByText(/Dernier Prévol : valid/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Activer|Suspendre|Prévol/ })).not.toBeInTheDocument()
    unmount()

    render(<AutomationExceptionsPage session={session} />)
    expect(await screen.findByRole('heading', { name: 'Entrées et exceptions à traiter' })).toBeInTheDocument()
    expect(screen.getByRole('listitem')).toHaveTextContent('Atelier Alpha')
    expect(screen.getByRole('listitem')).toHaveTextContent('owner_unavailable')
    expect(screen.getByRole('listitem')).toHaveTextContent('Ouverte')
  })

  it('autorise seulement le Prévol persistant aux rôles habilités, sans action d’activation', async () => {
    automationApi.listPlaybooks.mockResolvedValue({
      preflight_enabled: true,
      items: [{ code: 'new_prospect', state: 'preflight_required' }],
    })
    render(<AutomationPlaybooksPage session={{ ...session, capabilities: ['automation:preflights:run'] }} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Lancer un Prévol' }))
    expect(automationApi.runPreflight).toHaveBeenCalledWith('new_prospect', expect.any(String))
    expect(await screen.findByText(/Prévol enregistré sans effet CRM/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Activer|Suspendre/ })).not.toBeInTheDocument()
  })

  it('demande une confirmation avant une suspension versionnée', async () => {
    automationApi.listPlaybooks.mockResolvedValue({
      lifecycle_enabled: true,
      items: [{ code: 'new_prospect', state: 'active_prepare', version: 3 }],
    })
    render(<AutomationPlaybooksPage session={{ ...session, capabilities: ['automation:playbooks:suspend'] }} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Suspendre' }))
    expect(screen.getByText(/Confirmez cette transition/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(automationApi.transitionPlaybook).toHaveBeenCalledWith(
      'new_prospect', 'suspend', 3, expect.any(String), { reasonCode: 'operator_request' },
    )
    expect(await screen.findByText(/État du Playbook mis à jour/i)).toBeInTheDocument()
  })

  it('ouvre la sous-navigation mobile avec les trois destinations', () => {
    render(<AutomationWorkspace activeSection="today"><p>Contenu</p></AutomationWorkspace>)

    const trigger = screen.getByRole('button', { name: 'Sections Automatisation' })
    fireEvent.click(trigger)
    const dialog = screen.getByRole('dialog', { name: 'Automatisation' })
    expect(within(dialog).getByRole('link', { name: 'Aujourd’hui' })).toHaveAttribute('href', '/app/automation/today')
    expect(within(dialog).getByRole('link', { name: 'Playbooks' })).toHaveAttribute('href', '/app/automation/playbooks')
    expect(within(dialog).getByRole('link', { name: 'Entrées et exceptions' })).toHaveAttribute('href', '/app/automation/exceptions')
  })
})
