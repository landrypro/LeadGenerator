import { useCallback, useEffect, useMemo, useState } from 'react'

import { configureHttpSecurity } from '../../shared/api/httpClient'
import { authApi } from './api/authApi'
import { AuthContext } from './context'


export function AuthProvider({ children }) {
  const [status, setStatus] = useState('loading')
  const [session, setSession] = useState(null)

  const clearSession = useCallback(() => {
    configureHttpSecurity()
    setSession(null)
    setStatus('anonymous')
  }, [])

  const installSession = useCallback((nextSession) => {
    configureHttpSecurity({ token: nextSession.csrf_token, onUnauthorized: clearSession })
    setSession(nextSession)
    setStatus('authenticated')
    return nextSession
  }, [clearSession])

  useEffect(() => {
    const controller = new AbortController()
    configureHttpSecurity({ onUnauthorized: clearSession })
    authApi.me(controller.signal)
      .then(installSession)
      .catch((error) => {
        if (error?.name !== 'AbortError') clearSession()
      })
    return () => controller.abort()
  }, [clearSession, installSession])

  const login = useCallback(async (email, password) => {
    const authenticatedSession = await authApi.login(email, password)
    return installSession(authenticatedSession)
  }, [installSession])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      clearSession()
    }
  }, [clearSession])

  const value = useMemo(
    () => ({ status, session, login, logout, adoptSession: installSession }),
    [status, session, login, logout, installSession],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
