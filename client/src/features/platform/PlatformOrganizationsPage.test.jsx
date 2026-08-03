import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { platformApi } from './api/platformApi'
import { PlatformOrganizationsPage } from './PlatformOrganizationsPage'


vi.mock('./api/platformApi', () => ({ platformApi: { listOrganizations: vi.fn() } }))


describe('PlatformOrganizationsPage', () => {
  beforeEach(() => platformApi.listOrganizations.mockResolvedValue({ items: [], next_cursor: null }))

  it('masque le provisioning sans capacité de création', async () => {
    render(<PlatformOrganizationsPage session={{ capabilities: ['platform:organizations:read'] }} />)
    expect(screen.getByRole('heading', { name: 'Organisations' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Provisionner une organisation' })).not.toBeInTheDocument()
    expect(await screen.findByText('Aucune organisation accessible.')).toBeInTheDocument()
  })

  it('affiche le formulaire avec la capacité de création', () => {
    render(<PlatformOrganizationsPage session={{ capabilities: ['platform:organizations:read', 'platform:organizations:create'] }} />)
    expect(screen.getByRole('heading', { name: 'Provisionner une organisation' })).toBeInTheDocument()
  })
})
