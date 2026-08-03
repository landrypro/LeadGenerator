import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useContext } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, postJson } from '../../shared/api/httpClient'
import { AuthProvider } from './AuthContext'
import { authApi } from './api/authApi'
import { AuthContext } from './context'

vi.mock('./api/authApi', () => ({
  authApi: {
    login: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
    switchOrganization: vi.fn(),
  },
}))

const session = {
  user: { id: 'user-1', email: 'alex@example.ca', display_name: 'Alex', status: 'active', platform_role: null },
  active_organization: { id: 'organization-1', name: 'Exemple' },
  memberships: [],
  capabilities: ['google:search'],
  csrf_token: 'csrf-secret-kept-in-memory',
}

function Probe() {
  const auth = useContext(AuthContext)
  return <span>{auth.session?.user.display_name || auth.status}</span>
}


function SwitchProbe() {
  const auth = useContext(AuthContext)
  return <>
    <span>{auth.session?.active_organization?.name || auth.status}</span>
    <span>{auth.switchingOrganization ? 'commutation' : 'stable'}</span>
    <button type="button" onClick={() => auth.switchOrganization('membership-2').catch(() => {})}>Changer</button>
    <button type="button" onClick={auth.logout}>Quitter</button>
  </>
}


function SummaryProbe() {
  const auth = useContext(AuthContext)
  return <>
    <span>{auth.session?.active_organization?.name}</span>
    <span>{auth.session?.memberships[0]?.organization.name}</span>
    <button type="button" onClick={() => auth.updateActiveOrganizationSummary({
      id: 'organization-1',
      name: 'Nom validé par le serveur',
    })}>Actualiser le résumé</button>
  </>
}


describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('restaure la session sans écrire dans le stockage navigateur', async () => {
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem')
    authApi.me.mockResolvedValue(session)
    render(<AuthProvider><Probe /></AuthProvider>)

    expect(await screen.findByText('Alex')).toBeInTheDocument()
    expect(authApi.me).toHaveBeenCalledTimes(1)
    expect(storageWrite).not.toHaveBeenCalled()
    storageWrite.mockRestore()
  })

  it('revient à l’état anonyme après une réponse 401', async () => {
    authApi.me.mockRejectedValue(new ApiError('Authentification requise.', 401))
    render(<AuthProvider><Probe /></AuthProvider>)

    await waitFor(() => expect(screen.getByText('anonymous')).toBeInTheDocument())
  })

  it('installe atomiquement la nouvelle session et le nouveau CSRF', async () => {
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem')
    const nextSession = {
      ...session,
      active_organization: { id: 'organization-2', name: 'Deuxième organisation' },
      csrf_token: 'csrf-rotated-after-switch',
    }
    authApi.me.mockResolvedValue(session)
    authApi.switchOrganization.mockResolvedValue(nextSession)
    render(<AuthProvider><SwitchProbe /></AuthProvider>)
    expect(await screen.findByText('Exemple')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Changer' }))

    expect(await screen.findByText('Deuxième organisation')).toBeInTheDocument()
    expect(authApi.switchOrganization).toHaveBeenCalledTimes(1)
    expect(authApi.switchOrganization).toHaveBeenCalledWith('membership-2', expect.any(AbortSignal))

    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 })
    vi.stubGlobal('fetch', fetchMock)
    await postJson('/api/test', {})
    expect(fetchMock).toHaveBeenCalledWith('/api/test', expect.objectContaining({
      headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-rotated-after-switch' }),
    }))
    expect(storageWrite).not.toHaveBeenCalled()
    storageWrite.mockRestore()
  })

  it('neutralise les commutations concurrentes', async () => {
    const pending = deferred()
    authApi.me.mockResolvedValue(session)
    authApi.switchOrganization.mockReturnValue(pending.promise)
    render(<AuthProvider><SwitchProbe /></AuthProvider>)
    expect(await screen.findByText('Exemple')).toBeInTheDocument()

    const button = screen.getByRole('button', { name: 'Changer' })
    fireEvent.click(button)
    fireEvent.click(button)

    expect(authApi.switchOrganization).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('commutation')).toBeInTheDocument()
    pending.resolve({ ...session, active_organization: { id: 'organization-2', name: 'Deuxième organisation' } })
    expect(await screen.findByText('Deuxième organisation')).toBeInTheDocument()
  })

  it('conserve l’ancienne session lorsque la commutation échoue', async () => {
    authApi.me.mockResolvedValue(session)
    authApi.switchOrganization.mockRejectedValue(new ApiError('Commutation indisponible.', 503))
    render(<AuthProvider><SwitchProbe /></AuthProvider>)
    expect(await screen.findByText('Exemple')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Changer' }))

    await waitFor(() => expect(screen.getByText('stable')).toBeInTheDocument())
    expect(screen.getByText('Exemple')).toBeInTheDocument()
  })

  it('ignore une réponse tardive après déconnexion', async () => {
    const pending = deferred()
    authApi.me.mockResolvedValue(session)
    authApi.switchOrganization.mockReturnValue(pending.promise)
    authApi.logout.mockResolvedValue(null)
    render(<AuthProvider><SwitchProbe /></AuthProvider>)
    expect(await screen.findByText('Exemple')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Changer' }))
    fireEvent.click(screen.getByRole('button', { name: 'Quitter' }))
    expect(await screen.findByText('anonymous')).toBeInTheDocument()

    pending.resolve({ ...session, active_organization: { id: 'organization-2', name: 'Réponse tardive' } })
    await waitFor(() => expect(screen.queryByText('Réponse tardive')).not.toBeInTheDocument())
    expect(screen.getByText('anonymous')).toBeInTheDocument()
  })

  it('invalide la commutation dès le début d’une déconnexion lente', async () => {
    const pendingSwitch = deferred()
    const pendingLogout = deferred()
    authApi.me.mockResolvedValue(session)
    authApi.switchOrganization.mockReturnValue(pendingSwitch.promise)
    authApi.logout.mockReturnValue(pendingLogout.promise)
    render(<AuthProvider><SwitchProbe /></AuthProvider>)
    expect(await screen.findByText('Exemple')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Changer' }))
    fireEvent.click(screen.getByRole('button', { name: 'Quitter' }))
    pendingSwitch.resolve({ ...session, active_organization: { id: 'organization-2', name: 'Contexte interdit' } })

    await waitFor(() => expect(screen.queryByText('Contexte interdit')).not.toBeInTheDocument())
    expect(screen.getByText('Exemple')).toBeInTheDocument()

    pendingLogout.resolve(null)
    expect(await screen.findByText('anonymous')).toBeInTheDocument()
  })

  it('répercute un nom validé dans les résumés de la session active', async () => {
    authApi.me.mockResolvedValue({
      ...session,
      memberships: [{
        id: 'membership-1',
        organization: session.active_organization,
        role: 'admin',
      }],
    })
    render(<AuthProvider><SummaryProbe /></AuthProvider>)
    expect((await screen.findAllByText('Exemple'))).toHaveLength(2)

    fireEvent.click(screen.getByRole('button', { name: 'Actualiser le résumé' }))

    expect(screen.getAllByText('Nom validé par le serveur')).toHaveLength(2)
  })
})


function deferred() {
  let resolve
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}
