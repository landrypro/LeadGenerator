import { useEffect } from 'react'

import { X } from '../icons'


function focusableElements(dialog) {
  return [...dialog.querySelectorAll('a[href], button:not([disabled]), select:not([disabled]), summary, [tabindex]:not([tabindex="-1"])')]
    .filter(element => !element.hidden && element.getAttribute('aria-hidden') !== 'true')
}

export function NavigationDialog({ id = 'primary-navigation', open, dialogRef, closeButtonRef, title, closeLabel, onRequestClose, children, footer, className = '' }) {
  const titleId = `${id}-title`
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
      closeButtonRef.current?.focus()
    } else if (!open && dialog.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
    }
  }, [closeButtonRef, dialogRef, open])

  return <dialog
    ref={dialogRef}
    id={id}
    className={`authenticated-navigation-dialog ${className}`.trim()}
    aria-labelledby={titleId}
    aria-modal="true"
    onCancel={event => {
      event.preventDefault()
      onRequestClose()
    }}
    onClick={event => {
      if (event.target === event.currentTarget) onRequestClose()
    }}
    onKeyDown={event => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onRequestClose()
        return
      }
      if (event.key !== 'Tab' || typeof dialogRef.current?.showModal === 'function') return
      const focusable = focusableElements(dialogRef.current)
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable.at(-1)
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }}
  >
    <div className="authenticated-navigation-dialog-surface">
      <div className="authenticated-navigation-mobile-heading">
        <strong id={titleId}>{title}</strong>
        <button ref={closeButtonRef} type="button" onClick={onRequestClose} aria-label={closeLabel}>
          <X size={18} />
        </button>
      </div>
      {children}
      {footer && <div className="authenticated-navigation-dialog-footer">{footer}</div>}
    </div>
  </dialog>
}
