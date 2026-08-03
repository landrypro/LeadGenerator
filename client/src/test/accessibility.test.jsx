import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AuthenticatedLayout } from '../app/AuthenticatedLayout'
import { AccountPage } from '../features/account/AccountPage'
import { AccessDeniedPage } from '../features/auth/AccessDeniedPage'
import { LoginPage } from '../features/auth/LoginPage'
import { NoOrganizationPage } from '../features/auth/NoOrganizationPage'
import { NotFoundPage } from '../features/auth/NotFoundPage'
import { PlaceSearchPage } from '../features/lead-search/LeadGeneratorPage'
import { Notices } from '../features/lead-search/components/Notices'
import { ResultsCard } from '../features/lead-search/components/ResultsCard'
import { axeViolations, formatViolations } from './accessibility'


vi.mock('../features/lead-search/hooks/useApiHealth', () => ({ useApiHealth: () => true }))
vi.mock('../features/lead-search/hooks/useLeadSearch', () => ({
  useLeadSearch: () => ({ result: null, loading: false, runSearch: vi.fn() }),
}))


describe('accessibilité globale', () => {
  it.each([
    ['connexion', <LoginPage onLogin={vi.fn()} />],
    ['sans organisation', <NoOrganizationPage onLogout={vi.fn()} />],
    ['403', <AccessDeniedPage homePath="/app/account" />],
    ['404', <NotFoundPage homePath="/app/account" />],
    ['compte', <AccountPage session={session()} onLogout={vi.fn()} />],
    ['recherche', <PlaceSearchPage session={session()} />],
  ])('ne présente aucune violation axe sur %s', async (_name, element) => {
    const { container } = render(element)
    const violations = await axeViolations(container)
    expect(formatViolations(violations)).toEqual([])
  })

  it('ne présente aucune violation axe dans le shell authentifié', async () => {
    const { container } = render(<AuthenticatedLayout currentRoute={{ id: 'account', title: 'Mon compte' }} session={session()} onLogout={vi.fn()} onSwitchOrganization={vi.fn()}><AccountPage session={session()} onLogout={vi.fn()} /></AuthenticatedLayout>)
    const violations = await axeViolations(container)
    expect(formatViolations(violations)).toEqual([])
  })

  it('valide la navigation mobile ouverte', async () => {
    const { container } = render(<AuthenticatedLayout currentRoute={{ id: 'account', title: 'Mon compte' }} session={session()} onLogout={vi.fn()} onSwitchOrganization={vi.fn()}><AccountPage session={session()} onLogout={vi.fn()} /></AuthenticatedLayout>)
    fireEvent.click(screen.getByRole('button', { name: 'Menu' }))
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })

  it('valide les résultats Google et leur erreur contrôlée', async () => {
    const place = { place_id: 'place-1', name: 'Entreprise Exemple', address: 'Québec', primary_type: 'plumber', distance_km: 2, radius_verified: true, business_status: 'OPERATIONAL', google_maps_url: 'https://maps.google.com/?cid=1' }
    const { container } = render(<main><Notices error="Erreur contrôlée" keyReady onClearError={vi.fn()} /><ResultsCard places={[place]} result={{ places: [place] }} loading={false} /></main>)
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })
})


function session() {
  const organization = { id: 'org-1', name: 'Entreprise Exemple' }
  return {
    user: { id: 'user-1', display_name: 'Alex Exemple', email: 'alex@example.ca', platform_role: null },
    active_organization: organization,
    memberships: [{ id: 'membership-1', organization, role: 'admin' }],
    capabilities: ['google:search', 'google:map', 'organization:read'],
  }
}
