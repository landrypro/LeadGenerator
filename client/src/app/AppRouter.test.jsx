import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext } from '../features/auth/context'
import { AppRouter } from './AppRouter'


describe('AppRouter', () => {
  it('isole un compte authentifié sans organisation de toutes les routes fonctionnelles', () => {
    window.history.replaceState({}, '', '/')
    const auth = {
      status: 'authenticated',
      session: {
        user: {
          id: 'user-1',
          email: 'alex@example.ca',
          display_name: 'Alex',
          status: 'active',
          platform_role: null,
        },
        active_organization: null,
        memberships: [],
        capabilities: [],
        csrf_token: 'csrf-only-in-memory',
      },
      login: vi.fn(),
      logout: vi.fn(),
      adoptSession: vi.fn(),
    }

    render(<AuthContext.Provider value={auth}><AppRouter /></AuthContext.Provider>)

    expect(screen.getByRole('heading', { name: 'Aucune organisation accessible' })).toBeInTheDocument()
    expect(screen.queryByText('Recherche d’établissements')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Se déconnecter' })).toBeInTheDocument()
  })
})
