import { useContext, useEffect, useState } from 'react'

import { AuthContext } from '../features/auth/context'
import { AccessDeniedPage } from '../features/auth/AccessDeniedPage'
import { LoginPage } from '../features/auth/LoginPage'
import { SessionLoadingPage } from '../features/auth/SessionLoadingPage'
import { NoOrganizationPage } from '../features/auth/NoOrganizationPage'
import { InvitationPage } from '../features/invitations/InvitationPage'
import { currentPath, NAVIGATION_EVENT } from './navigation'
import { CRM_PATHS, routes } from './routes'


export function AppRouter({ invitationToken = '' }) {
  const auth = useContext(AuthContext)
  const [pathname, setPathname] = useState(currentPath)

  useEffect(() => {
    const synchronizePath = () => setPathname(currentPath())
    window.addEventListener('popstate', synchronizePath)
    window.addEventListener(NAVIGATION_EVENT, synchronizePath)
    return () => {
      window.removeEventListener('popstate', synchronizePath)
      window.removeEventListener(NAVIGATION_EVENT, synchronizePath)
    }
  }, [])

  if (pathname === CRM_PATHS.acceptInvitation) {
    return <InvitationPage initialToken={invitationToken} auth={auth} />
  }
  if (!auth || auth.status === 'loading') return <SessionLoadingPage />
  if (!auth.session) return <LoginPage onLogin={auth.login} />
  if (!auth.session.active_organization) {
    return <NoOrganizationPage onLogout={auth.logout} />
  }

  const route = routes.find((candidate) => candidate.path === pathname) ?? routes[0]
  if (route.requiredCapability && !auth.session.capabilities.includes(route.requiredCapability)) {
    return <AccessDeniedPage onLogout={auth.logout} />
  }
  const RouteComponent = route.Component
  return <RouteComponent session={auth.session} onLogout={auth.logout} />
}
