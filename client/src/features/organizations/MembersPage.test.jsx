import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../shared/api/httpClient'
import { organizationApi } from './api/organizationApi'
import { useInvitations } from './hooks/useInvitations'
import { useMembers } from './hooks/useMembers'
import { MembersPage } from './MembersPage'


vi.mock('./api/organizationApi', () => ({
  organizationApi: {
    updateMember: vi.fn(),
    createInvitation: vi.fn(),
    resendInvitation: vi.fn(),
    revokeInvitation: vi.fn(),
  },
}))

vi.mock('./hooks/useMembers', () => ({ useMembers: vi.fn() }))
vi.mock('./hooks/useInvitations', () => ({ useInvitations: vi.fn() }))

const baseMember = {
  membership_id: 'membership-2',
  user: { id: 'user-2', email: 'membre@example.ca', display_name: 'Membre Exemple' },
  role: 'admin',
  status: 'active',
  version: 3,
  created_at: '2026-08-01T14:00:00Z',
  updated_at: '2026-08-02T14:00:00Z',
}


describe('MembersPage', () => {
  let memberResource

  beforeEach(() => {
    vi.clearAllMocks()
    window.history.replaceState({}, '', '/app/admin/users')
    memberResource = members([baseMember])
    useMembers.mockReturnValue(memberResource)
    useInvitations.mockReturnValue(invitations())
  })

  it('rend la liste strictement en lecture seule pour un Gestionnaire', () => {
    render(<MembersPage session={session(['members:read'])} />)

    expect(screen.getByText('Membre Exemple')).toBeInTheDocument()
    expect(screen.getByText('membre@example.ca')).toBeInTheDocument()
    expect(screen.getAllByRole('time')).toHaveLength(2)
    expect(screen.queryByRole('button', { name: 'Modifier' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Invitations' })).not.toBeInTheDocument()
  })

  it('confirme le retrait Admin puis envoie la version et le seul champ modifié', async () => {
    const updated = { ...baseMember, role: 'manager', version: 4 }
    organizationApi.updateMember.mockResolvedValue(updated)
    render(<MembersPage session={session(['members:read', 'members:manage'])} />)

    fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'Rôle' }), { target: { value: 'manager' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le membre' }))

    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(organizationApi.updateMember).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la modification' }))

    await waitFor(() => expect(organizationApi.updateMember).toHaveBeenCalledWith(
      'membership-2',
      { version: 3, role: 'manager' },
      expect.any(AbortSignal),
    ))
    expect(memberResource.reconcile).toHaveBeenCalledWith(updated)
  })

  it('explique la protection du dernier Administrateur sans modifier la ligne', async () => {
    organizationApi.updateMember.mockRejectedValue(new ApiError(
      'Dernier administrateur.',
      409,
      'last_active_administrator',
    ))
    render(<MembersPage session={session(['members:read', 'members:manage'])} />)
    fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'État' }), { target: { value: 'disabled' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le membre' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la modification' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('conserver un autre Administrateur actif')
    expect(memberResource.reconcile).not.toHaveBeenCalled()
  })

  it('préserve la saisie sur conflit et recharge sans rejouer la mutation', async () => {
    const salesMember = { ...baseMember, role: 'sales' }
    memberResource = members([salesMember])
    memberResource.refresh.mockResolvedValue({ items: [{ ...salesMember, version: 4 }], next_cursor: null })
    useMembers.mockReturnValue(memberResource)
    organizationApi.updateMember.mockRejectedValue(new ApiError(
      'Version obsolète.',
      409,
      'membership_version_conflict',
      { version: '4' },
    ))
    render(<MembersPage session={session(['members:read', 'members:manage'])} />)
    fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
    const role = screen.getByRole('combobox', { name: 'Rôle' })
    fireEvent.change(role, { target: { value: 'manager' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le membre' }))

    expect(await screen.findByText(/Version chargée : 3.*Version actuelle : 4/)).toBeInTheDocument()
    expect(role).toHaveValue('manager')
    fireEvent.click(screen.getByRole('button', { name: 'Recharger la liste avant de continuer' }))
    await waitFor(() => expect(memberResource.refresh).toHaveBeenCalledTimes(1))
    expect(organizationApi.updateMember).toHaveBeenCalledTimes(1)
  })

  it('vide immédiatement la session après sa propre modification', async () => {
    const ownMember = { ...baseMember, user: { ...baseMember.user, id: 'user-1' }, role: 'sales' }
    memberResource = members([ownMember])
    useMembers.mockReturnValue(memberResource)
    organizationApi.updateMember.mockResolvedValue({ ...ownMember, role: 'manager', version: 4 })
    const onSessionInvalidated = vi.fn()
    render(<MembersPage
      session={session(['members:read', 'members:manage'])}
      onSessionInvalidated={onSessionInvalidated}
    />)
    fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'Rôle' }), { target: { value: 'manager' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le membre' }))

    await waitFor(() => expect(onSessionInvalidated).toHaveBeenCalledTimes(1))
    expect(window.location.pathname).toBe('/login')
  })

  it('affiche les invitations uniquement avec les capacités correspondantes', () => {
    render(<MembersPage session={session([
      'members:read', 'members:manage', 'invitations:read', 'invitations:manage',
    ])} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Invitations' }))

    expect(screen.getByRole('heading', { name: 'Inviter une personne' })).toBeInTheDocument()
    expect(useInvitations).toHaveBeenCalledWith(true)
  })

  it('navigue entre les onglets au clavier avec un seul tab actif', () => {
    render(<MembersPage session={session(['members:read', 'invitations:read'])} />)
    const tabList = screen.getByRole('tablist', { name: 'Administration des accès' })
    const membersTab = screen.getByRole('tab', { name: 'Membres' })
    const invitationsTab = screen.getByRole('tab', { name: 'Invitations' })
    membersTab.focus()

    fireEvent.keyDown(tabList, { key: 'ArrowRight' })
    expect(invitationsTab).toHaveFocus()
    expect(invitationsTab).toHaveAttribute('aria-selected', 'true')
    expect(membersTab).toHaveAttribute('tabindex', '-1')
    expect(screen.getByRole('tabpanel', { name: 'Invitations' })).toBeVisible()

    fireEvent.keyDown(tabList, { key: 'Home' })
    expect(membersTab).toHaveFocus()
    expect(membersTab).toHaveAttribute('tabindex', '0')
  })

  it('conserve une intention ambiguë pendant un simple changement d’onglet', async () => {
    organizationApi.createInvitation
      .mockRejectedValueOnce(new ApiError('Incertain.', 503, 'invitation_outcome_unknown'))
      .mockResolvedValueOnce({
        id: 'invitation-1', recipient_email: 'invitee@example.ca', role: 'sales', state: 'active',
        delivery_status: 'sent', expires_at: '2026-08-06T14:00:00Z', created_at: '2026-08-03T14:00:00Z',
      })
    const createId = vi.fn().mockReturnValue('request-stable-tab')
    render(<MembersPage
      createId={createId}
      session={session(['members:read', 'invitations:read', 'invitations:manage'])}
    />)
    fireEvent.click(screen.getByRole('tab', { name: 'Invitations' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Adresse courriel' }), { target: { value: 'invitee@example.ca' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’invitation' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Membres' }))
    fireEvent.click(screen.getByRole('tab', { name: 'Invitations' }))
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’invitation' }))

    await waitFor(() => expect(organizationApi.createInvitation).toHaveBeenCalledTimes(2))
    expect(organizationApi.createInvitation.mock.calls[0][0].invitation_request_id).toBe('request-stable-tab')
    expect(organizationApi.createInvitation.mock.calls[1][0].invitation_request_id).toBe('request-stable-tab')
    expect(createId).toHaveBeenCalledTimes(1)
  })
})


function session(capabilities) {
  return {
    user: { id: 'user-1', email: 'admin@example.ca', display_name: 'Admin', platform_role: null },
    active_organization: { id: 'organization-1', name: 'Entreprise' },
    memberships: [],
    capabilities,
  }
}


function members(items) {
  return {
    items,
    nextCursor: null,
    loading: false,
    refreshing: false,
    loadingMore: false,
    error: '',
    refresh: vi.fn(),
    loadMore: vi.fn(),
    reconcile: vi.fn(),
  }
}


function invitations() {
  return {
    items: [],
    nextCursor: null,
    loading: false,
    refreshing: false,
    loadingMore: false,
    error: '',
    refresh: vi.fn(),
    loadMore: vi.fn(),
    upsert: vi.fn(),
    remove: vi.fn(),
  }
}
