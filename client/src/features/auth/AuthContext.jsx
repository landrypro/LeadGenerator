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

  const installSession = useCallback(async (nextSession, signal) => {
    const installationGeneration = ++sessionGenerationRef.current
    configureHttpSecurity({ token: nextSession.csrf_token, onUnauthorized: clearSession })
    let installedSession = nextSession
    const capabilities = nextSession.capabilities ?? []
    const canReadAutomation = capabilities.includes('automation:read:self') || capabilities.includes('automation:plan:create')
    if (nextSession.active_organization && canReadAutomation && typeof authApi.getAutomationAvailability === 'function') {
      try {
        const availability = await authApi.getAutomationAvailability(signal)
        installedSession = { ...nextSession, automation_available: availability.effective_enabled === true }
      } catch (error) {
        if (error?.name === 'AbortError') throw error
        // Do not make a failed availability probe log the user out. The route
        // capability checks remain the server-side source of truth.
      }
    }
    if (sessionGenerationRef.current !== installationGeneration) return null
    setSession(installedSession)
    setStatus('authenticated')
    return installedSession
  }, [clearSession])

  useEffect(() => {
    const controller = new AbortController()
    configureHttpSecurity({ onUnauthorized: clearSession })
    authApi.me(controller.signal)
      .then((nextSession) => installSession(nextSession, controller.signal))
      .catch((error) => {
        if (error?.name !== 'AbortError') clearSession()
      })
    return () => controller.abort()
  }, [clearSession, installSession])

  useEffect(() => () => switchControllerRef.current?.abort(), [])

  const login = useCallback(async (email, password, locale = 'fr-CA') => {
    const authenticatedSession = await authApi.login(email, password, locale)
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
        return installSession(nextSession, controller.signal)
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
        active_organization: {
          ...currentSession.active_organization,
          name: organization.name,
          locale: organization.locale,
          timezone: organization.timezone,
        },
        memberships: currentSession.memberships.map((membership) => (
          membership.organization.id === organization.id
            ? {
                ...membership,
                organization: {
                  ...membership.organization,
                  name: organization.name,
                  locale: organization.locale,
                  timezone: organization.timezone,
                },
              }
            : membership
        )),
      }
    })
  }, [])

  const updateAutomationAvailability = useCallback((available) => {
    setSession((currentSession) => currentSession ? { ...currentSession, automation_available: available === true } : currentSession)
  }, [])

  const value = useMemo(
    () => ({
      status,
      session,
      login,
      logout,
      adoptSession: installSession,
      invalidateSession: clearSession,
      switchOrganization,
      switchingOrganization,
      updateActiveOrganizationSummary,
      updateAutomationAvailability,
    }),
    [
      status,
      session,
      login,
      logout,
      installSession,
      clearSession,
      switchOrganization,
      switchingOrganization,
      updateActiveOrganizationSummary,
      updateAutomationAvailability,
    ],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
