import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
  beforeEach(() => {
    window.localStorage.setItem('marketteo.public-locale.v1', 'fr-CA')
    window.history.replaceState({}, '', '/app/search')
  })
  it('propose Compte et la déconnexion sans organisation', () => {
    const onLogout = vi.fn()
    render(<AuthenticatedLayout currentRoute={findRoute('/app/account')} session={{ ...session, active_organization: null, capabilities: [] }} onLogout={onLogout}><main>Compte</main></AuthenticatedLayout>)
    expect(screen.queryByText('Acquisition', { selector: 'summary' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Alex', { selector: 'summary' }))
    expect(screen.getByRole('link', { name: 'Compte' })).toHaveAttribute('href', '/app/account')
    fireEvent.click(screen.getByRole('button', { name: 'Se déconnecter' }))
    expect(onLogout).toHaveBeenCalledOnce()
  })

  it('ferme un groupe avec Échap, au clic extérieur et au changement de capacités', () => {
    const props = { currentRoute: findRoute('/app/search'), session, onLogout: vi.fn(), children: <main>Contenu</main> }
    const { rerender } = render(<AuthenticatedLayout {...props} />)
    const summary = screen.getByText('Acquisition', { selector: 'summary' })
    fireEvent.click(summary)
    expect(summary.parentElement).toHaveAttribute('open')
    fireEvent.keyDown(summary, { key: 'Escape' })
    expect(summary.parentElement).not.toHaveAttribute('open')
    expect(summary).toHaveFocus()
    fireEvent.click(summary)
    fireEvent.pointerDown(screen.getByText('Contenu'))
    expect(summary.parentElement).not.toHaveAttribute('open')
    fireEvent.click(summary)
    rerender(<AuthenticatedLayout {...props} session={{ ...session, capabilities: ['platform:audit:read'], active_organization: null }} />)
    expect(screen.queryByText('Acquisition', { selector: 'summary' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Audit plateforme' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Plateforme' })).not.toBeInTheDocument()
  })

  it('localise les groupes et indique le parent actif', () => {
    render(<AuthenticatedLayout currentRoute={findRoute('/app/usage')} session={{ ...session, active_organization: { ...session.active_organization, locale: 'en-CA' }, capabilities: ['usage:read:self'] }} onLogout={vi.fn()}><main>Content</main></AuthenticatedLayout>)
    const group = screen.getByText(/Data and audit/, { selector: 'summary' })
    expect(group.parentElement).toHaveClass('is-active')
    fireEvent.click(group)
    expect(screen.getByRole('link', { name: 'Quotas and usage' })).toHaveAttribute('aria-current', 'page')
  })

  it('rend une navigation sémantique limitée aux capacités', () => {
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/search')}
      session={session}
      onLogout={vi.fn()}
    ><main>Contenu</main></AuthenticatedLayout>)

    const navigation = screen.getByRole('navigation', { name: 'Navigation principale' })
    expect(navigation).toHaveTextContent('Recherche d’établissements')
    expect(navigation).not.toHaveTextContent('Compte')
    fireEvent.click(screen.getByText('Acquisition', { selector: 'summary' }))
    expect(screen.queryByText('Administration plateforme')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Recherche d’établissements' })).toHaveAttribute('aria-current', 'page')
  })

  it('ouvre un dialogue modal, ferme avec Échap et restitue le focus', async () => {
    const historyBack = vi.spyOn(window.history, 'back').mockImplementation(() => {})
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/search')}
      session={session}
      onLogout={vi.fn()}
    ><main>Contenu</main></AuthenticatedLayout>)

    const menuButton = screen.getByRole('button', { name: 'Menu' })
    fireEvent.click(menuButton)
    expect(menuButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'Fermer la navigation' })).toHaveFocus()
    const dialog = screen.getByRole('dialog', { name: 'Navigation' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')

    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(menuButton).toHaveAttribute('aria-expanded', 'false')
    await waitFor(() => expect(menuButton).toHaveFocus())
    expect(historyBack).toHaveBeenCalledOnce()
    historyBack.mockRestore()
  })

  it('filtre les raccourcis mobiles par capacités tout en conservant Plus', () => {
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/tasks')}
      session={{ ...session, capabilities: ['dashboard:read:self', 'tasks:read', 'prospects:read'] }}
      onLogout={vi.fn()}
    ><main>Contenu</main></AuthenticatedLayout>)

    const mobileNavigation = screen.getByRole('navigation', { name: 'Navigation mobile' })
    expect(within(mobileNavigation).getAllByRole('link').map(link => link.textContent)).toEqual(['Accueil', 'Tâches', 'Prospects'])
    expect(within(mobileNavigation).queryByRole('link', { name: 'Pipeline' })).not.toBeInTheDocument()
    expect(within(mobileNavigation).getByRole('button', { name: 'Plus' })).toBeInTheDocument()
    expect(within(mobileNavigation).getByRole('link', { name: 'Tâches' })).toHaveAttribute('aria-current', 'page')
  })

  it('ferme le dialogue lorsque Retour est reçu et rend le focus au déclencheur Plus', async () => {
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/search')}
      session={session}
      onLogout={vi.fn()}
    ><main>Contenu</main></AuthenticatedLayout>)

    const more = screen.getByRole('button', { name: 'Plus' })
    fireEvent.click(more)
    expect(screen.getByRole('dialog', { name: 'Navigation' })).toBeInTheDocument()
    fireEvent.popState(window)
    expect(more).toHaveAttribute('aria-expanded', 'false')
    await waitFor(() => expect(more).toHaveFocus())
  })

  it('remplace l’entrée modale lors d’une navigation pour ne pas créer de doublon dans l’historique', () => {
    const replaceState = vi.spyOn(window.history, 'replaceState')
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/account')}
      session={{ ...session, capabilities: ['dashboard:read:self'] }}
      onLogout={vi.fn()}
    ><main>Compte</main></AuthenticatedLayout>)

    fireEvent.click(screen.getByRole('button', { name: 'Plus' }))
    const dialog = screen.getByRole('dialog', { name: 'Navigation' })
    fireEvent.click(within(dialog).getByRole('link', { name: 'Tableau de bord' }))
    expect(window.location.pathname).toBe('/app/dashboard')
    expect(replaceState).toHaveBeenLastCalledWith({}, '', '/app/dashboard')
    replaceState.mockRestore()
  })

  it('propose un lien d’évitement vers le contenu', () => {
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/account')}
      session={session}
      onLogout={vi.fn()}
    ><main>Contenu</main></AuthenticatedLayout>)

    expect(screen.getByRole('link', { name: 'Aller au contenu principal' })).toHaveAttribute('href', '#route-content')
  })

  it('donne accès au manuel utilisateur dans un nouvel onglet', () => {
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/account')}
      session={session}
      onLogout={vi.fn()}
    ><main>Contenu</main></AuthenticatedLayout>)

    const manual = screen.getByRole('link', { name: 'Manuel' })
    expect(manual).toHaveAttribute('href', '/manuel-utilisateur/index.html')
    expect(manual).toHaveAttribute('target', '_blank')
    expect(manual).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('traduit la route Opportunités dans la navigation et le fil d’Ariane', () => {
    render(<AuthenticatedLayout
      currentRoute={findRoute('/app/opportunities')}
      session={{
        ...session,
        active_organization: { ...session.active_organization, locale: 'en-CA' },
        capabilities: ['opportunities:read'],
      }}
      onLogout={vi.fn()}
    ><main>Content</main></AuthenticatedLayout>)

    expect(screen.getByRole('link', { name: 'Opportunities' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Opportunities')
  })
})
