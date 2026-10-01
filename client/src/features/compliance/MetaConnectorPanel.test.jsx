import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { connectorApi } from './api/connectorApi'
import { MetaConnectorPanel } from './MetaConnectorPanel'

vi.mock('./api/connectorApi', () => ({
  connectorApi: {
    list: vi.fn(), create: vi.fn(), submit: vi.fn(), review: vi.fn(), disable: vi.fn(),
  },
}))

const session = {
  capabilities: ['providers:manage', 'providers:review'],
  active_organization: { locale: 'fr-CA' },
}

describe('MetaConnectorPanel', () => {
  beforeEach(() => {
    connectorApi.list.mockResolvedValue({ items: [] })
  })

  it('ne propose pas l’approbation au créateur du brouillon', async () => {
    connectorApi.list.mockResolvedValue({ items: [{
      id: 'contract-1', status: 'pending_review', is_creator: true,
      requested_permissions: ['full_name'], binding_status: 'draft', version: 2,
    }] })

    render(<MetaConnectorPanel session={session} providers={[]} acquisitions={[]} />)

    expect(await screen.findByText('Une autre personne disposant de la capacité de revue doit approuver ce brouillon.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approuver' })).toBeNull()
  })

  it('propose l’approbation à un autre réviseur autorisé', async () => {
    connectorApi.list.mockResolvedValue({ items: [{
      id: 'contract-1', status: 'pending_review', is_creator: false,
      requested_permissions: ['full_name'], binding_status: 'draft', version: 2,
    }] })

    render(<MetaConnectorPanel session={session} providers={[]} acquisitions={[]} />)

    expect(await screen.findByRole('button', { name: 'Approuver' })).toBeInTheDocument()
  })
})
