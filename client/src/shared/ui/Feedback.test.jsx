import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ErrorBanner } from './Feedback'


describe('ErrorBanner', () => {
  it('annonce l’erreur et reçoit le focus à son apparition', () => {
    render(<ErrorBanner><span>Erreur contrôlée</span></ErrorBanner>)
    expect(screen.getByRole('alert')).toHaveFocus()
  })
})
