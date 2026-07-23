import { render, screen, waitFor } from '@testing-library/react'
import { useContext } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../shared/api/httpClient'
import { AuthProvider } from './AuthContext'
import { authApi } from './api/authApi'
import { AuthContext } from './context'

vi.mock('./api/authApi', () => ({
  authApi: {
    login: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
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


describe('AuthProvider', () => {
  beforeEach(() => vi.clearAllMocks())

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
})
