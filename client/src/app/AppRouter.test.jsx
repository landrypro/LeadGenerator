import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext } from '../features/auth/context'
import { AppRouter } from './AppRouter'


vi.mock('../features/lead-search/LeadGeneratorPage', () => ({
  PlaceSearchPage: () => <main><h1>Recherche d’établissements</h1></main>,
}))

vi.mock('../features/organizations/OrganizationPage', () => ({
  OrganizationPage: () => <main><h1>Fiche de l’organisation</h1></main>,
}))

vi.mock('../features/organizations/MembersPage', () => ({
  MembersPage: () => <main><h1>Administration des membres</h1></main>,
}))

vi.mock('../features/platform/PlatformOrganizationsPage', () => ({
  PlatformOrganizationsPage: () => <main><h1>Organisations de la plateforme</h1></main>,
}))


describe('AppRouter', () => {
  it('redirige une visite anonyme vers la route de connexion', async () => {
    window.history.replaceState({}, '', '/')
    renderRouter(anonymousAuth())

    expect(await screen.findByRole('heading', { name: 'Connexion' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
  })

  it('redirige la racine vers la recherche pour une organisation autorisée', async () => {
    window.history.replaceState({}, '', '/')
    renderRouter(authenticatedSession({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['google:search'],
    }))

    expect(await screen.findByRole('heading', { name: 'Recherche d’établissements' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/app/search')
    expect(screen.getByRole('navigation', { name: 'Navigation principale' })).toBeInTheDocument()
  })

  it('redirige un utilisateur authentifié hors de la page de connexion', async () => {
    window.history.replaceState({}, '', '/login')
    renderRouter(authenticatedSession({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['google:search'],
    }))

    expect(await screen.findByRole('heading', { name: 'Recherche d’établissements' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/app/search')
  })

  it('isole à la racine un compte sans organisation ni rôle plateforme', () => {
    window.history.replaceState({}, '', '/')
    renderRouter(authenticatedSession({ activeOrganization: null }))

    expect(screen.getByRole('heading', { name: 'Aucune organisation accessible' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Navigation principale' })).not.toBeInTheDocument()
    expect(screen.queryByText('Recherche d’établissements')).not.toBeInTheDocument()
  })

  it('dirige un administrateur plateforme sans organisation vers la plateforme', async () => {
    window.history.replaceState({}, '', '/')
    renderRouter(authenticatedSession({
      activeOrganization: null,
      capabilities: ['platform:organizations:read', 'platform:organizations:create'],
      platformRole: 'platform_admin',
    }))

    expect(await screen.findByRole('heading', { name: 'Organisations de la plateforme' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/app/platform/organizations')
    expect(screen.queryByText('Recherche d’établissements')).not.toBeInTheDocument()
  })

  it('ouvre la plateforme uniquement avec sa capacité de lecture', () => {
    window.history.replaceState({}, '', '/app/platform/organizations')
    renderRouter(authenticatedSession({ activeOrganization: null, capabilities: ['platform:organizations:read'], platformRole: 'platform_admin' }))

    expect(screen.getByRole('heading', { name: 'Organisations de la plateforme' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Plateforme' })).toHaveAttribute('aria-current', 'page')
  })

  it('affiche un refus contrôlé sans la capacité google:search', () => {
    window.history.replaceState({}, '', '/app/search')
    renderRouter(authenticatedSession({ activeOrganization: { id: 'org-1', name: 'Entreprise' } }))

    expect(screen.getByRole('heading', { name: 'Accès non autorisé' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Recherche d’établissements' })).not.toBeInTheDocument()
  })

  it('ouvre la page Organisation avec la capacité de lecture', () => {
    window.history.replaceState({}, '', '/app/admin/organization')
    renderRouter(authenticatedSession({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['organization:read'],
    }))

    expect(screen.getByRole('heading', { name: 'Fiche de l’organisation' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Organisation' })).toHaveAttribute('aria-current', 'page')
  })

  it('ouvre la page Membres uniquement avec la capacité de lecture', () => {
    window.history.replaceState({}, '', '/app/admin/users')
    renderRouter(authenticatedSession({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['members:read'],
    }))

    expect(screen.getByRole('heading', { name: 'Administration des membres' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Membres' })).toHaveAttribute('aria-current', 'page')
  })

  it('affiche une vraie page 404 pour une route inconnue', () => {
    window.history.replaceState({}, '', '/route-inconnue')
    renderRouter(authenticatedSession({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['google:search'],
    }))

    expect(screen.getByRole('heading', { name: 'Page introuvable' })).toBeInTheDocument()
    expect(screen.queryByText('Recherche d’établissements')).not.toBeInTheDocument()
    expect(window.location.pathname).toBe('/route-inconnue')
  })

  it('restaure la route lors d’un événement retour ou avance', async () => {
    window.history.replaceState({}, '', '/app/search')
    renderRouter(authenticatedSession({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['google:search'],
    }))
    expect(screen.getByRole('heading', { name: 'Recherche d’établissements' })).toBeInTheDocument()

    window.history.replaceState({}, '', '/app/account')
    window.dispatchEvent(new PopStateEvent('popstate'))

    expect(await screen.findByRole('heading', { name: 'Mon compte' })).toBeInTheDocument()
  })

  it('ne montre aucune navigation privilégiée pendant la restauration de session', () => {
    window.history.replaceState({}, '', '/app/search')
    renderRouter({ status: 'loading', session: null, login: vi.fn(), logout: vi.fn() })

    expect(screen.getByText('Vérification de la session…')).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('filtre la navigation et permet de rejoindre la page Compte', async () => {
    window.history.replaceState({}, '', '/app/search')
    renderRouter(authenticatedSession({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['google:search'],
    }))

    expect(screen.getByRole('link', { name: 'Recherche Google' })).toHaveAttribute('aria-current', 'page')
    expect(screen.queryByRole('link', { name: /Organisation|Membres|Plateforme/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: 'Compte' }))

    expect(await screen.findByRole('heading', { name: 'Mon compte' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/app/account')
  })
})


function renderRouter(auth) {
  return render(<AuthContext.Provider value={auth}><AppRouter /></AuthContext.Provider>)
}


function anonymousAuth() {
  return { status: 'anonymous', session: null, login: vi.fn(), logout: vi.fn(), adoptSession: vi.fn() }
}


function authenticatedSession({ activeOrganization, capabilities = [], platformRole = null }) {
  return {
    status: 'authenticated',
    session: {
      user: {
        id: 'user-1',
        email: 'alex@example.ca',
        display_name: 'Alex',
        status: 'active',
        platform_role: platformRole,
      },
      active_organization: activeOrganization,
      memberships: activeOrganization ? [{
        id: 'membership-1',
        organization: activeOrganization,
        role: 'admin',
      }] : [],
      capabilities,
      csrf_token: 'csrf-only-in-memory',
    },
    login: vi.fn(),
    logout: vi.fn(),
    adoptSession: vi.fn(),
  }
}
