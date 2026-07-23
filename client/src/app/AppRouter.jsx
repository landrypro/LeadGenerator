import { useContext, useEffect, useState } from 'react'

import { AuthContext } from '../features/auth/context'
import { LoginPage } from '../features/auth/LoginPage'
import { SessionLoadingPage } from '../features/auth/SessionLoadingPage'
import { currentPath, NAVIGATION_EVENT } from './navigation'
import { routes } from './routes'


export function AppRouter() {
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

  if (!auth || auth.status === 'loading') return <SessionLoadingPage />
  if (!auth.session) return <LoginPage onLogin={auth.login} />

  const route = routes.find((candidate) => candidate.path === pathname) ?? routes[0]
  const RouteComponent = route.Component
  return <RouteComponent session={auth.session} onLogout={auth.logout} />
}
