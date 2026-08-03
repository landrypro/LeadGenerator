import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AccountPage } from './AccountPage'


const session = {
  user: {
    id: 'user-secret-id',
    email: 'alex@example.ca',
    display_name: 'Alex Tremblay',
    status: 'active',
    platform_role: 'platform_admin',
  },
  active_organization: { id: 'organization-secret-id', name: 'Entreprise Boréale' },
  memberships: [{
    id: 'membership-secret-id',
    organization: { id: 'organization-secret-id', name: 'Entreprise Boréale' },
    role: 'admin',
  }],
  capabilities: ['google:search'],
  csrf_token: 'csrf-secret-kept-in-memory',
}


describe('AccountPage', () => {
  it('affiche uniquement les informations de session utiles', () => {
    render(<AccountPage session={session} onLogout={vi.fn()} />)

    expect(screen.getByText('Alex Tremblay')).toBeInTheDocument()
    expect(screen.getByText('alex@example.ca')).toBeInTheDocument()
    expect(screen.getByText('Administrateur de plateforme')).toBeInTheDocument()
    expect(screen.getAllByText('Entreprise Boréale')).toHaveLength(2)
    expect(screen.getByText('Administrateur')).toBeInTheDocument()
    expect(screen.queryByText('csrf-secret-kept-in-memory')).not.toBeInTheDocument()
    expect(screen.queryByText('user-secret-id')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('permet de demander la déconnexion', () => {
    const logout = vi.fn()
    render(<AccountPage session={session} onLogout={logout} />)

    fireEvent.click(screen.getByRole('button', { name: 'Se déconnecter' }))
    expect(logout).toHaveBeenCalledTimes(1)
  })
})
