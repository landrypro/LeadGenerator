import { useContext, useEffect, useState } from 'react'

import { AuthContext } from '../features/auth/context'
import { AccessDeniedPage } from '../features/auth/AccessDeniedPage'
import { LoginPage } from '../features/auth/LoginPage'
import { NotFoundPage } from '../features/auth/NotFoundPage'
import { SessionLoadingPage } from '../features/auth/SessionLoadingPage'
import { NoOrganizationPage } from '../features/auth/NoOrganizationPage'
import { InvitationPage } from '../features/invitations/InvitationPage'
import { AuthenticatedLayout } from './AuthenticatedLayout'
import { currentPath, navigate, NAVIGATION_EVENT } from './navigation'
import { canAccessRoute, CRM_PATHS, findRoute, landingPath } from './routes'


function Redirect({ to, onRedirect }) {
  useEffect(() => {
    navigate(to, { replace: true })
    onRedirect(to)
  }, [onRedirect, to])
  return <SessionLoadingPage message="Redirection…" />
}


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

  useEffect(() => {
    const routeTitle = findRoute(pathname)?.title
    const pageTitle = pathname === CRM_PATHS.login
      ? 'Connexion'
      : pathname === CRM_PATHS.acceptInvitation
        ? 'Invitation'
        : routeTitle ?? (pathname === CRM_PATHS.home ? 'Accueil' : 'Page introuvable')
    document.title = `${pageTitle} — Prospect CRM`
  }, [pathname])

  if (pathname === CRM_PATHS.acceptInvitation) {
    return <InvitationPage initialToken={invitationToken} auth={auth} />
  }
  if (!auth || auth.status === 'loading') return <SessionLoadingPage />
  if (!auth.session) {
    if (pathname !== CRM_PATHS.login) return <Redirect to={CRM_PATHS.login} onRedirect={setPathname} />
    return <LoginPage onLogin={auth.login} />
  }

  const homePath = landingPath(auth.session)
  if (pathname === CRM_PATHS.home || pathname === CRM_PATHS.login) {
    if (!auth.session.active_organization && !auth.session.user.platform_role && pathname === CRM_PATHS.home) {
      return <NoOrganizationPage onLogout={auth.logout} />
    }
    return <Redirect to={homePath} onRedirect={setPathname} />
  }

  const route = findRoute(pathname)
  let content
  if (!route) {
    content = <NotFoundPage homePath={homePath} />
  } else if (!canAccessRoute(route, auth.session)) {
    content = <AccessDeniedPage homePath={homePath} />
  } else {
    const RouteComponent = route.Component
    content = <RouteComponent
      key={auth.session.active_organization?.id ?? 'without-organization'}
      session={auth.session}
      onLogout={auth.logout}
      onOrganizationUpdated={auth.updateActiveOrganizationSummary}
    />
  }

  return <AuthenticatedLayout
    currentRoute={route}
    session={auth.session}
    onLogout={auth.logout}
    onSwitchOrganization={auth.switchOrganization}
    switchingOrganization={auth.switchingOrganization}
  >{content}</AuthenticatedLayout>
}
