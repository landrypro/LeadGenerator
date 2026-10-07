import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { automationApi } from './api/automationApi'
import { AutomationSettingsPage } from './AutomationSettingsPage'


vi.mock('./api/automationApi', () => ({
  automationApi: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
  },
}))


const settings = {
  schema_version: 1,
  global_enabled: true,
  assistant_enabled: true,
  assistant_available: false,
  rollout_mode: 'all',
  effective_enabled: false,
  item: {
    id: 'settings-1', organization_id: 'organization-1', automation_enabled: false,
    suspension_generation: 0, version: 1, created_at: null, updated_at: null,
  },
}


describe('AutomationSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    automationApi.getSettings.mockResolvedValue(settings)
  })

  it('affiche l’état de l’organisation et demande une confirmation avant mutation', async () => {
    const onAutomationAvailabilityChanged = vi.fn()
    automationApi.updateSettings.mockResolvedValue({
      ...settings,
      effective_enabled: true,
      assistant_available: true,
      item: { ...settings.item, automation_enabled: true, version: 2 },
    })
    render(<AutomationSettingsPage session={session()} onAutomationAvailabilityChanged={onAutomationAvailabilityChanged} />)

    expect(await screen.findByRole('heading', { name: 'Automatisation' })).toBeInTheDocument()
    expect(screen.getByText('Suspendue')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Activer l’Automatisation' }))
    expect(screen.getByText(/Confirmez l’activation/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))

    await waitFor(() => expect(automationApi.updateSettings).toHaveBeenCalledWith(true, 1))
    expect(onAutomationAvailabilityChanged).toHaveBeenLastCalledWith(expect.objectContaining({
      effective_enabled: true,
      assistant_available: true,
    }))
    expect(await screen.findByRole('status')).toHaveTextContent('enregistrés')
  })

  it('n’expose pas de commande pour une session sans capacité de gestion', async () => {
    render(<AutomationSettingsPage session={session(['automation:read:self'])} />)
    expect(await screen.findByRole('heading', { name: 'Automatisation' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Activer|Suspendre/ })).not.toBeInTheDocument()
  })
})


function session(capabilities = ['automation:settings:manage']) {
  return {
    active_organization: { id: 'organization-1', name: 'Entreprise Exemple', locale: 'fr-CA' },
    capabilities,
  }
}
