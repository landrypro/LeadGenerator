export const NAVIGATION_EVENT = 'prospect:navigation'


export function normalizePath(pathname) {
  if (!pathname || pathname === '/') return '/'
  const withoutTrailingSlashes = pathname.replace(/\/+$/, '')
  return withoutTrailingSlashes || '/'
}


export function currentPath() {
  return normalizePath(window.location.pathname)
}


export function navigate(path, { replace = false } = {}) {
  const target = normalizePath(path)
  if (currentPath() === target) return
  const method = replace ? 'replaceState' : 'pushState'
  window.history[method]({}, '', target)
  window.dispatchEvent(new Event(NAVIGATION_EVENT))
}


export function followInternalLink(event, path) {
  if (
    event.defaultPrevented
    || event.button !== 0
    || event.metaKey
    || event.ctrlKey
    || event.shiftKey
    || event.altKey
  ) return
  event.preventDefault()
  navigate(path)
}
