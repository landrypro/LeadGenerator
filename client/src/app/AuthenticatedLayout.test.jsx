import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AuthenticatedLayout } from './AuthenticatedLayout'
import { findRoute } from './routes'


const session = {
  user: {
    id: 'user-1',
    email: 'alex@example.ca',
    display_name: 'Alex',
    status: 'active',
    platform_role: null,
  },
  active_organization: { id: 'org-1', name: 'Entreprise Exemple' },
  memberships: [],
  capabilities: ['google:search'],
  csrf_token: 'csrf-kept-in-memory',
}


describe('AuthenticatedLayout', () => {
  it('rend une navigation sémantique limitée aux capacités', () => {
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/search')}
      session={session}
      onLogout={vi.fn()}
    ><main>Contenu</main></AuthenticatedLayout>)

    const navigation = screen.getByRole('navigation', { name: 'Navigation principale' })
    expect(navigation).toHaveTextContent('Recherche Google')
    expect(navigation).toHaveTextContent('Compte')
    expect(screen.queryByText('Administration plateforme')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Recherche Google' })).toHaveAttribute('aria-current', 'page')
  })

  it('ferme le menu mobile avec Échap et restitue le focus', () => {
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/search')}
      session={session}
      onLogout={vi.fn()}
    ><main>Contenu</main></AuthenticatedLayout>)

    const menuButton = screen.getByRole('button', { name: 'Menu' })
    fireEvent.click(menuButton)
    expect(menuButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'Fermer la navigation' })).toHaveFocus()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(menuButton).toHaveAttribute('aria-expanded', 'false')
    expect(menuButton).toHaveFocus()
  })

  it('propose un lien d’évitement vers le contenu', () => {
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/account')}
      session={session}
      onLogout={vi.fn()}
    ><main>Contenu</main></AuthenticatedLayout>)

    expect(screen.getByRole('link', { name: 'Aller au contenu principal' })).toHaveAttribute('href', '#route-content')
  })
})
