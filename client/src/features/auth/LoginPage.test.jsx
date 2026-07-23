import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { LoginPage } from './LoginPage'


describe('LoginPage', () => {
  it('offre un formulaire accessible et transmet les identifiants sans les conserver', async () => {
    const onLogin = vi.fn().mockResolvedValue(undefined)
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem')
    render(<LoginPage onLogin={onLogin} />)

    fireEvent.change(screen.getByLabelText('Adresse courriel'), { target: { value: 'alex@example.ca' } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'mot-de-passe-confidentiel' } })
    fireEvent.click(screen.getByRole('button', { name: 'Se connecter' }))

    await waitFor(() => expect(onLogin).toHaveBeenCalledWith('alex@example.ca', 'mot-de-passe-confidentiel'))
    expect(screen.getByLabelText('Adresse courriel')).toHaveAttribute('autocomplete', 'username')
    expect(screen.getByLabelText('Mot de passe')).toHaveAttribute('autocomplete', 'current-password')
    expect(storageWrite).not.toHaveBeenCalled()
    storageWrite.mockRestore()
  })

  it('affiche une erreur générique dans une zone annoncée', async () => {
    const onLogin = vi.fn().mockRejectedValue(new Error('Courriel ou mot de passe incorrect.'))
    render(<LoginPage onLogin={onLogin} />)

    fireEvent.change(screen.getByLabelText('Adresse courriel'), { target: { value: 'alex@example.ca' } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'incorrect' } })
    fireEvent.click(screen.getByRole('button', { name: 'Se connecter' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Courriel ou mot de passe incorrect.')
  })
})
