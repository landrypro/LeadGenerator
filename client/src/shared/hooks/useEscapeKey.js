import { useEffect } from 'react'


export function useEscapeKey(enabled, callback) {
  useEffect(() => {
    if (!enabled) return undefined
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') callback()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [enabled, callback])
}
