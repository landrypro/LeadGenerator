import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { opportunityApi } from '../opportunities/api/opportunityApi'
import { prospectApi } from './api/prospectApi'
import { ProspectDetailPage } from './ProspectDetailPage'


vi.mock('./api/prospectApi', () => ({
  prospectApi: {
    get: vi.fn(), listContacts: vi.fn(), listChannels: vi.fn(), listContactChannels: vi.fn(), getPermission: vi.fn(), listTimeline: vi.fn(),
  },
}))

vi.mock('../opportunities/api/opportunityApi', () => ({
  opportunityApi: {
    listForProspect: vi.fn(), transition: vi.fn(),
  },
}))


describe('ProspectDetailPage', () => {
  beforeEach(() => {
    prospectApi.get.mockResolvedValue({
      id: 'prospect-1', internal_alias: 'Atelier Nord', industry_label: 'Construction', city: 'Québec', priority: 2, tags: ['prioritaire'], version: 1,
    })
    prospectApi.listContacts.mockResolvedValue({ items: [{ id: 'contact-1', display_name: 'Camille Tremblay', role_label: 'Direction' }] })
    prospectApi.listChannels.mockResolvedValue([{ id: 'channel-prospect', channel_type: 'phone', value: '+14185550100', provenance_id: 'source-1' }])
    prospectApi.listContactChannels.mockResolvedValue([{ id: 'channel-contact', channel_type: 'email', value: 'camille@example.ca', provenance_id: 'source-2' }])
    prospectApi.getPermission.mockResolvedValue({ id: 'permission-1', status: 'unknown', version: 1 })
    prospectApi.listTimeline.mockResolvedValue({
      activities: [],
      tasks: [],
      task_events: [],
      transitions: [{ id: 'transition-1', from_stage: 'new', to_stage: 'qualifying', occurred_at: '2026-09-05T14:00:00Z' }],
    })
    opportunityApi.listForProspect.mockResolvedValue({ items: [], aggregates_by_currency: [] })
  })

  it('affiche le profil, les contacts et les canaux sans divulguer de données Google', async () => {
    render(<ProspectDetailPage routeParams={{ prospectId: 'prospect-1' }} session={{ active_organization: { locale: 'fr-CA', timezone: 'America/Toronto' }, capabilities: ['prospects:read', 'prospects:update', 'contacts:read', 'contacts:write', 'permissions:allow', 'permissions:restrict', 'activities:read', 'activities:create'] }} />)

    expect(await screen.findByRole('heading', { name: 'Atelier Nord' })).toBeInTheDocument()
    expect(screen.getAllByText('Camille Tremblay')).toHaveLength(2)
    expect(screen.getByText(/camille@example.ca/)).toBeInTheDocument()
    expect(screen.getByText('+14185550100')).toBeInTheDocument()
    expect(screen.getByLabelText('Associer le canal à')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Chronologie commerciale' })).toBeInTheDocument()
    expect(screen.getByText('Nouveau → Qualification')).toBeInTheDocument()
    expect(prospectApi.listContactChannels).toHaveBeenCalledWith('contact-1', expect.any(AbortSignal))
  })

  it('retire le succès précédent lorsqu’une transition opportunité échoue', async () => {
    const qualification = {
      id: 'opportunity-1', name: 'Victoire OPP-05', amount: '15000.0000', currency_code: 'CAD', probability: 60,
      stage_code: 'qualification', expected_close_on: '2026-09-20', overdue: false, version: 2,
    }
    const proposal = { ...qualification, stage_code: 'proposal', version: 3 }
    opportunityApi.listForProspect
      .mockResolvedValueOnce({ items: [qualification], aggregates_by_currency: [] })
      .mockResolvedValueOnce({ items: [proposal], aggregates_by_currency: [] })
    opportunityApi.transition
      .mockResolvedValueOnce(proposal)
      .mockRejectedValueOnce(new Error('La commande opportunité est invalide.'))

    render(<ProspectDetailPage routeParams={{ prospectId: 'prospect-1' }} session={{
      user: { id: 'user-1' },
      active_organization: { locale: 'fr-CA', timezone: 'America/Toronto' },
      capabilities: ['prospects:read', 'contacts:read', 'opportunities:read', 'opportunities:update', 'opportunities:close'],
    }} />)

    fireEvent.change(await screen.findByLabelText('Étape Victoire OPP-05'), { target: { value: 'proposal' } })
    expect(await screen.findByText('L’étape de l’opportunité a été mise à jour.')).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Gagnée' }))

    expect(await screen.findByText('La commande opportunité est invalide.')).toBeInTheDocument()
    expect(screen.queryByText('L’étape de l’opportunité a été mise à jour.')).not.toBeInTheDocument()
  })
})
