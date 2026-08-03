import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ConfirmationDialog } from './ConfirmationDialog'


describe('ConfirmationDialog', () => {
  it('piège le focus, ferme avec Échap et restitue le focus', () => {
    const onCancel = vi.fn()
    const { rerender } = render(<><button type="button">Ouvrir</button></>)
    const trigger = screen.getByRole('button', { name: 'Ouvrir' })
    trigger.focus()
    rerender(<><button type="button">Ouvrir</button><ConfirmationDialog title="Confirmer" confirmLabel="Continuer" onCancel={onCancel} onConfirm={vi.fn()}><p>Description.</p></ConfirmationDialog></>)
    const confirm = screen.getByRole('button', { name: 'Continuer' })
    const cancel = screen.getByRole('button', { name: 'Annuler' })
    expect(confirm).toHaveFocus()

    fireEvent.keyDown(confirm, { key: 'Tab' })
    expect(cancel).toHaveFocus()
    fireEvent.keyDown(cancel, { key: 'Tab', shiftKey: true })
    expect(confirm).toHaveFocus()
    fireEvent.keyDown(confirm, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalledTimes(1)

    rerender(<><button type="button">Ouvrir</button></>)
    expect(trigger).toHaveFocus()
  })

  it('maintient le focus dans le dialogue pendant une action occupée', () => {
    const onCancel = vi.fn()
    render(<><button type="button">Arrière-plan</button><ConfirmationDialog busy title="Traitement" confirmLabel="Continuer" onCancel={onCancel} onConfirm={vi.fn()}><p>Description.</p></ConfirmationDialog></>)
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveFocus()

    fireEvent.keyDown(dialog, { key: 'Tab' })
    expect(dialog).toHaveFocus()
    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(onCancel).not.toHaveBeenCalled()
  })
})
