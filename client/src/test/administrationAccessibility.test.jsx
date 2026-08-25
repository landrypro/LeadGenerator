import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { MembersPage } from '../features/organizations/MembersPage'
import { OrganizationPage } from '../features/organizations/OrganizationPage'
import { ConfirmationDialog } from '../features/organizations/components/ConfirmationDialog'
import { PlatformOrganizationsPage } from '../features/platform/PlatformOrganizationsPage'
import { ProvidersAcquisitionsPage } from '../features/compliance/ProvidersAcquisitionsPage'
import { RetentionImportsPage } from '../features/retention/RetentionImportsPage'
import { axeViolations, formatViolations } from './accessibility'


const ORGANIZATION = organization()


vi.mock('../features/organizations/hooks/useOrganization', () => ({
  useOrganization: () => ({ organization: ORGANIZATION, setOrganization: vi.fn(), loading: false, error: '', load: vi.fn() }),
}))
vi.mock('../features/organizations/hooks/useMembers', () => ({ useMembers: () => resource([member()]) }))
vi.mock('../features/organizations/hooks/useInvitations', () => ({ useInvitations: () => ({ ...resource([invitation()]), upsert: vi.fn(), remove: vi.fn() }) }))
vi.mock('../features/platform/hooks/usePlatformOrganizations', () => ({ usePlatformOrganizations: () => ({ ...resource([provisioning()]), upsert: vi.fn() }) }))
vi.mock('../features/compliance/api/complianceApi', () => ({ complianceApi: { listProviders: vi.fn().mockResolvedValue({ items: [] }), listAcquisitions: vi.fn().mockResolvedValue({ items: [] }) } }))
vi.mock('../features/retention/api/retentionApi', () => ({ retentionApi: { listPolicies: vi.fn().mockResolvedValue({ items: [] }), listReviews: vi.fn().mockResolvedValue({ items: [] }), listHolds: vi.fn().mockResolvedValue({ items: [] }), listImports: vi.fn().mockResolvedValue({ items: [] }) } }))


describe('accessibilité de l’administration', () => {
  it('valide Organisation en édition', async () => assertAccessible(<OrganizationPage session={session(['organization:read', 'organization:update'])} onOrganizationUpdated={vi.fn()} />))

  it('valide Organisation en lecture seule', async () => assertAccessible(<OrganizationPage session={session(['organization:read'])} onOrganizationUpdated={vi.fn()} />))

  it('valide Membres et l’onglet Invitations', async () => {
    const { container } = render(<MembersPage session={session(['members:read', 'members:manage', 'invitations:read', 'invitations:manage'])} />)
    expect(formatViolations(await axeViolations(container))).toEqual([])
    fireEvent.click(screen.getByRole('tab', { name: 'Invitations' }))
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })

  it('valide Membres en lecture Gestionnaire', async () => assertAccessible(<MembersPage session={session(['members:read'])} />))

  it('valide Plateforme avec provisioning', async () => assertAccessible(<PlatformOrganizationsPage session={session(['platform:organizations:read', 'platform:organizations:create'])} />))

  it('valide Plateforme en lecture seule', async () => assertAccessible(<PlatformOrganizationsPage session={session(['platform:organizations:read'])} />))

  it('valide le dialogue réel de révocation plateforme', async () => {
    const { container } = render(<PlatformOrganizationsPage session={session(['platform:organizations:read', 'platform:organizations:create'])} />)
    fireEvent.click(screen.getByRole('button', { name: 'Révoquer' }))
    expect(screen.getByRole('alertdialog', { name: 'Révoquer cette invitation initiale ?' })).toBeInTheDocument()
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })

  it('valide le dialogue de confirmation', async () => assertAccessible(<main><button type="button">Déclencheur</button><ConfirmationDialog title="Confirmer l’action" confirmLabel="Confirmer" onCancel={vi.fn()} onConfirm={vi.fn()}><p>Cette action est sensible.</p></ConfirmationDialog></main>))

  it('valide Fournisseurs et acquisitions', async () => {
    const { container } = render(<ProvidersAcquisitionsPage session={session(['providers:read', 'providers:manage', 'acquisitions:declare', 'acquisitions:review'])} />)
    await screen.findByRole('heading', { name: 'Fournisseurs enregistrés' })
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })

  it('valide Conservation et déclarations d’import', async () => {
    const { container } = render(<RetentionImportsPage session={session(['retention:read', 'retention:manage', 'retention:hold:create', 'retention:hold:release', 'imports:read', 'imports:declare', 'imports:archive'])} />)
    await screen.findByRole('heading', { name: 'Politiques' })
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })
})


async function assertAccessible(element) {
  const { container } = render(element)
  expect(formatViolations(await axeViolations(container))).toEqual([])
}


function resource(items) {
  return { items, loading: false, refreshing: false, loadingMore: false, error: '', nextCursor: null, refresh: vi.fn(), loadMore: vi.fn(), reconcile: vi.fn(), setItems: vi.fn() }
}


function session(capabilities) {
  return { user: { id: 'user-1', display_name: 'Alex', email: 'alex@example.ca', platform_role: 'platform_admin' }, active_organization: { id: 'org-1', name: 'Entreprise' }, memberships: [], capabilities }
}


function organization() {
  return { id: 'org-1', name: 'Entreprise Exemple', locale: 'fr-CA', timezone: 'America/Toronto', status: 'active', version: 2, created_at: '2026-08-01T12:00:00Z', updated_at: '2026-08-03T12:00:00Z' }
}


function member() {
  return { membership_id: 'membership-1', role: 'admin', status: 'active', version: 1, created_at: '2026-08-01T12:00:00Z', updated_at: '2026-08-03T12:00:00Z', user: { id: 'user-2', display_name: 'Morgan', email: 'morgan@example.ca' } }
}


function invitation() {
  return { id: 'invitation-1', recipient_email: 'invitee@example.ca', role: 'sales', state: 'active', delivery_status: 'sent', expires_at: '2026-08-06T12:00:00Z' }
}


function provisioning() {
  return { organization: { ...organization(), status: 'provisioning', activated_at: null }, first_invitation: { ...invitation(), role: 'admin' }, replayed: false }
}
