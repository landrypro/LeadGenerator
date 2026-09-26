import { useRef } from 'react'

// Native disclosure, with ordinary links (not an ARIA application menu).
export function NavigationDisclosure({ label, active = false, children, className = '', defaultOpen = false }) {
  const ref = useRef(null)
  return <details ref={ref} open={defaultOpen || undefined} className={`navigation-disclosure ${active ? 'is-active' : ''} ${className}`}
    onKeyDown={event => {
      if (event.key === 'Escape' && ref.current.open) {
        event.preventDefault()
        event.stopPropagation()
        ref.current.open = false
        ref.current.querySelector('summary').focus()
      }
    }}
    onClick={event => {
      const target = event.target.closest('a, button')
      if (target && event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) ref.current.open = false
    }}>
    <summary>{label}{active && <span className="navigation-active-marker" aria-hidden="true"> •</span>}</summary>
    <div className="navigation-disclosure-content">{children}</div>
  </details>
}
