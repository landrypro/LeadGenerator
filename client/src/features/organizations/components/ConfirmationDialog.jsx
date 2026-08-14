import { useEffect, useRef } from 'react'


export function ConfirmationDialog({ busy = false, children, confirmLabel, onCancel, onConfirm, title }) {
  const cancelRef = useRef(null)
  const confirmRef = useRef(null)
  const dialogRef = useRef(null)
  const returnFocusRef = useRef(null)

  useEffect(() => {
    returnFocusRef.current = document.activeElement
    confirmRef.current?.focus()
    return () => returnFocusRef.current?.focus?.()
  }, [])

  useEffect(() => {
    if (busy) dialogRef.current?.focus()
  }, [busy])

  function handleKeyDown(event) {
    if (event.key === 'Escape' && !busy) onCancel()
    if (event.key !== 'Tab') return
    const focusable = Array.from(dialogRef.current?.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex="-1"])') ?? [])
    if (busy) {
      event.preventDefault()
      dialogRef.current?.focus()
      return
    }
    const first = focusable[0] ?? confirmRef.current
    const last = focusable.at(-1) ?? cancelRef.current
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last?.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first?.focus()
    }
  }

  return <div className="confirmation-overlay" role="presentation">
    <section
      ref={dialogRef}
      className="confirmation-dialog"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirmation-title"
      aria-describedby="confirmation-description"
      tabIndex="-1"
      onKeyDown={handleKeyDown}
    >
      <h2 id="confirmation-title">{title}</h2>
      <div id="confirmation-description">{children}</div>
      <div className="confirmation-actions">
        <button ref={cancelRef} className="secondary-button" type="button" onClick={onCancel} disabled={busy}>Annuler</button>
        <button ref={confirmRef} className="danger-button" type="button" onClick={onConfirm} disabled={busy}>
          {busy ? 'Traitement…' : confirmLabel}
        </button>
      </div>
    </section>
  </div>
}
