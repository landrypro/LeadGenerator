import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { prospectApi } from './api/prospectApi'
import { ProspectDetailPage } from './ProspectDetailPage'


vi.mock('./api/prospectApi', () => ({
  prospectApi: {
    get: vi.fn(), listContacts: vi.fn(), listChannels: vi.fn(), listContactChannels: vi.fn(), getPermission: vi.fn(), listTimeline: vi.fn(),
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
})
