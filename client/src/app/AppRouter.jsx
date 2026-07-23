import { useEffect, useState } from 'react'

import { currentPath, NAVIGATION_EVENT } from './navigation'
import { routes } from './routes'


export function AppRouter() {
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

  const route = routes.find((candidate) => candidate.path === pathname) ?? routes[0]
  const RouteComponent = route.Component
  return <RouteComponent />
}
