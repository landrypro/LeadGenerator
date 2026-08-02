import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode, useMemo, useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../shared/api/httpClient'
import { navigate } from '../../app/navigation'
import { invitationApi } from './api/invitationApi'
import { InvitationPage } from './InvitationPage'

vi.mock('./api/invitationApi', () => ({
  invitationApi: {
    preview: vi.fn(),
    acceptNewAccount: vi.fn(),
    acceptExistingAccount: vi.fn(),
  },
}))

vi.mock('../../app/navigation', () => ({ navigate: vi.fn() }))

const token = 'A'.repeat(43)
const acceptedSession = {
  user: { id: 'user-1', email: 'alex@example.ca', display_name: 'Alex', status: 'active', platform_role: null },
  active_organization: { id: 'organization-1', name: 'Entreprise Exemple' },
  memberships: [],
  capabilities: ['google:search'],
  csrf_token: 'csrf-only-in-memory',
}

function anonymousAuth(overrides = {}) {
  return {
    status: 'anonymous',
    session: null,
    login: vi.fn(),
    logout: vi.fn(),
    adoptSession: vi.fn(),
    ...overrides,
  }
}


describe('InvitationPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('prévisualise une seule fois sous StrictMode et accepte un nouveau compte sans stockage navigateur', async () => {
    const preview = {
      organization_name: 'Entreprise Exemple',
      role: 'admin',
      expires_at: '2026-07-26T12:00:00Z',
      existing_account: false,
    }
    invitationApi.preview.mockImplementation((_token, signal) => new Promise((resolve, reject) => {
      const abort = () => reject(new DOMException('Aborted', 'AbortError'))
      signal.addEventListener('abort', abort, { once: true })
      queueMicrotask(() => {
        signal.removeEventListener('abort', abort)
        if (!signal.aborted) resolve(preview)
      })
    }))
    invitationApi.acceptNewAccount.mockResolvedValue(acceptedSession)
    const auth = anonymousAuth()
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem')

    render(<StrictMode><InvitationPage initialToken={token} auth={auth} /></StrictMode>)

    expect(await screen.findByText('Entreprise Exemple')).toBeInTheDocument()
    expect(invitationApi.preview).toHaveBeenCalledTimes(1)
    fireEvent.change(screen.getByLabelText('Nom affiché'), { target: { value: 'Alex Tremblay' } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'mot-de-passe-tres-solide' } })
    fireEvent.change(screen.getByLabelText('Confirmer le mot de passe'), {
      target: { value: 'mot-de-passe-tres-solide' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le compte et accepter' }))

    await waitFor(() => expect(invitationApi.acceptNewAccount).toHaveBeenCalledWith(
      token,
      'Alex Tremblay',
      'mot-de-passe-tres-solide',
    ))
    expect(auth.adoptSession).toHaveBeenCalledWith(acceptedSession)
    expect(navigate).toHaveBeenCalledWith('/')
    expect(storageWrite).not.toHaveBeenCalled()
    storageWrite.mockRestore()
  })

  it('connecte un compte existant sur place puis accepte sans navigation intermédiaire', async () => {
    invitationApi.preview.mockResolvedValue({
      organization_name: 'Entreprise Exemple',
      role: 'admin',
      expires_at: '2026-07-26T12:00:00Z',
      existing_account: true,
    })
    invitationApi.acceptExistingAccount.mockResolvedValue(acceptedSession)

    function Harness() {
      const [session, setSession] = useState(null)
      const auth = useMemo(() => ({
        status: session ? 'authenticated' : 'anonymous',
        session,
        login: async () => setSession({ ...acceptedSession, active_organization: null }),
        logout: vi.fn(),
        adoptSession: vi.fn(),
      }), [session])
      return <InvitationPage initialToken={token} auth={auth} />
    }

    render(<Harness />)
    expect(await screen.findByText('Entreprise Exemple')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Adresse courriel'), { target: { value: 'alex@example.ca' } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'mot-de-passe' } })
    fireEvent.click(screen.getByRole('button', { name: 'Se connecter' }))

    expect(await screen.findByRole('button', { name: 'Accepter l’invitation' })).toBeInTheDocument()
    expect(navigate).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Accepter l’invitation' }))

    await waitFor(() => expect(invitationApi.acceptExistingAccount).toHaveBeenCalledWith(token))
    expect(navigate).toHaveBeenCalledWith('/')
  })

  it('n’appelle pas le serveur sans jeton et rend les erreurs terminales accessibles', async () => {
    const { unmount } = render(<InvitationPage initialToken="" auth={anonymousAuth()} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Invitation non disponible')
    expect(invitationApi.preview).not.toHaveBeenCalled()

    invitationApi.preview.mockRejectedValue(new ApiError('masqué', 400, 'invitation_invalid'))
    unmount()
    render(<InvitationPage initialToken={token} auth={anonymousAuth()} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('invalide, expirée ou a déjà été utilisée')
    expect(screen.queryByText(token)).not.toBeInTheDocument()
  })
})
