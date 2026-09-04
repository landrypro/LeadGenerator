import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { prospectApi } from './api/prospectApi'
import { ProspectDetailPage } from './ProspectDetailPage'


vi.mock('./api/prospectApi', () => ({
  prospectApi: {
    get: vi.fn(), listContacts: vi.fn(), listChannels: vi.fn(), listContactChannels: vi.fn(), getPermission: vi.fn(),
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
  })

  it('affiche le profil, les contacts et les canaux sans divulguer de données Google', async () => {
    render(<ProspectDetailPage routeParams={{ prospectId: 'prospect-1' }} session={{ capabilities: ['prospects:read', 'prospects:update', 'contacts:read', 'contacts:write', 'permissions:allow', 'permissions:restrict'] }} />)

    expect(await screen.findByRole('heading', { name: 'Atelier Nord' })).toBeInTheDocument()
    expect(screen.getAllByText('Camille Tremblay')).toHaveLength(2)
    expect(screen.getByText(/camille@example.ca/)).toBeInTheDocument()
    expect(screen.getByText('+14185550100')).toBeInTheDocument()
    expect(screen.getByLabelText('Associer le canal à')).toBeInTheDocument()
    expect(prospectApi.listContactChannels).toHaveBeenCalledWith('contact-1', expect.any(AbortSignal))
  })
})
