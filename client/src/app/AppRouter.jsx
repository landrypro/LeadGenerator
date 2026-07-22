import { useEffect, useState } from 'react'

import { routes } from './routes'

const NAVIGATION_EVENT = 'prospect:navigation'


function currentPath() {
  return window.location.pathname.replace(/\/$/, '') || '/'
}


export function navigate(path) {
  if (currentPath() === path) return
  window.history.pushState({}, '', path)
  window.dispatchEvent(new Event(NAVIGATION_EVENT))
}


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
