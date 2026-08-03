import { render, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { InvitationPage } from '../features/invitations/InvitationPage'
import { invitationApi } from '../features/invitations/api/invitationApi'
import { axeViolations, formatViolations } from './accessibility'


vi.mock('../features/invitations/api/invitationApi', () => ({ invitationApi: { preview: vi.fn(), acceptNewAccount: vi.fn(), acceptExistingAccount: vi.fn() } }))


describe('accessibilité de l’invitation', () => {
  it('valide la vérification en cours', async () => {
    invitationApi.preview.mockReturnValue(new Promise(() => {}))
    const { container } = render(<InvitationPage initialToken="token-test" auth={{ status: 'loading', session: null }} />)
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })

  it('valide le formulaire de création de compte', async () => {
    invitationApi.preview.mockResolvedValue({ organization_name: 'Entreprise Exemple', role: 'admin', expires_at: '2026-08-06T12:00:00Z', existing_account: false })
    const { container } = render(<InvitationPage initialToken="token-test" auth={{ status: 'anonymous', session: null, login: vi.fn(), logout: vi.fn(), adoptSession: vi.fn() }} />)
    await waitFor(() => expect(container.querySelector('#invitation-name')).toBeInTheDocument())
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })

  it('valide l’état terminal sans jeton', async () => {
    const { container } = render(<InvitationPage initialToken="" auth={null} />)
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })
})
