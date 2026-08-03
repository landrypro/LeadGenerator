import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { configureHttpSecurity } from '../../shared/api/httpClient'
import { authApi } from './api/authApi'
import { AuthContext } from './context'


export function AuthProvider({ children }) {
  const [status, setStatus] = useState('loading')
  const [session, setSession] = useState(null)
  const [switchingOrganization, setSwitchingOrganization] = useState(false)
  const sessionGenerationRef = useRef(0)
  const switchPromiseRef = useRef(null)
  const switchControllerRef = useRef(null)

  const clearSession = useCallback(() => {
    sessionGenerationRef.current += 1
    switchControllerRef.current?.abort()
    switchControllerRef.current = null
    switchPromiseRef.current = null
    configureHttpSecurity()
    setSession(null)
    setStatus('anonymous')
    setSwitchingOrganization(false)
  }, [])

  const installSession = useCallback((nextSession) => {
    sessionGenerationRef.current += 1
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

  useEffect(() => () => switchControllerRef.current?.abort(), [])

  const login = useCallback(async (email, password) => {
    const authenticatedSession = await authApi.login(email, password)
    return installSession(authenticatedSession)
  }, [installSession])

  const logout = useCallback(async () => {
    // Invalider immédiatement une rotation en cours, tout en conservant le
    // CSRF assez longtemps pour authentifier la commande de déconnexion.
    sessionGenerationRef.current += 1
    switchControllerRef.current?.abort()
    switchControllerRef.current = null
    switchPromiseRef.current = null
    setSwitchingOrganization(false)
    try {
      await authApi.logout()
    } finally {
      clearSession()
    }
  }, [clearSession])

  const switchOrganization = useCallback((membershipId) => {
    if (switchPromiseRef.current) return switchPromiseRef.current

    const controller = new AbortController()
    const expectedGeneration = sessionGenerationRef.current
    switchControllerRef.current = controller
    setSwitchingOrganization(true)

    const switchPromise = (async () => {
      try {
        const nextSession = await authApi.switchOrganization(membershipId, controller.signal)
        if (sessionGenerationRef.current !== expectedGeneration) return null
        return installSession(nextSession)
      } finally {
        if (switchPromiseRef.current === switchPromise) {
          switchPromiseRef.current = null
          switchControllerRef.current = null
          setSwitchingOrganization(false)
        }
      }
    })()
    switchPromiseRef.current = switchPromise
    return switchPromise
  }, [installSession])

  const updateActiveOrganizationSummary = useCallback((organization) => {
    setSession((currentSession) => {
      if (!currentSession?.active_organization || currentSession.active_organization.id !== organization.id) {
        return currentSession
      }
      return {
        ...currentSession,
        active_organization: { ...currentSession.active_organization, name: organization.name },
        memberships: currentSession.memberships.map((membership) => (
          membership.organization.id === organization.id
            ? { ...membership, organization: { ...membership.organization, name: organization.name } }
            : membership
        )),
      }
    })
  }, [])

  const value = useMemo(
    () => ({
      status,
      session,
      login,
      logout,
      adoptSession: installSession,
      switchOrganization,
      switchingOrganization,
      updateActiveOrganizationSummary,
    }),
    [
      status,
      session,
      login,
      logout,
      installSession,
      switchOrganization,
      switchingOrganization,
      updateActiveOrganizationSummary,
    ],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
