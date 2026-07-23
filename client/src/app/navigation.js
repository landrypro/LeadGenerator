export const NAVIGATION_EVENT = 'prospect:navigation'


export function currentPath() {
  return window.location.pathname.replace(/\/$/, '') || '/'
}


export function navigate(path) {
  if (currentPath() === path) return
  window.history.pushState({}, '', path)
  window.dispatchEvent(new Event(NAVIGATION_EVENT))
}
