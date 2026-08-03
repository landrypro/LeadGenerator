import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { OrganizationSwitcher } from './OrganizationSwitcher'


const memberships = [
  { id: 'membership-a', organization: { id: 'organization-a', name: 'Organisation A' }, role: 'admin' },
  { id: 'membership-b', organization: { id: 'organization-b', name: 'Organisation B' }, role: 'manager' },
]

const session = {
  user: { id: 'user-1', display_name: 'Alex' },
  active_organization: memberships[0].organization,
  memberships,
  capabilities: ['google:search', 'organization:read'],
}


describe('OrganizationSwitcher', () => {
  beforeEach(() => window.history.replaceState({}, '', '/app/search'))

  it('reste discret avec une seule appartenance', () => {
    render(<OrganizationSwitcher
      session={{ ...session, memberships: memberships.slice(0, 1) }}
      switching={false}
      onSwitch={vi.fn()}
    />)

    expect(screen.getByText('Organisation A')).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Organisation active' })).not.toBeInTheDocument()
  })

  it('envoie exclusivement l’identifiant d’appartenance sélectionné', async () => {
    const nextSession = { ...session, active_organization: memberships[1].organization }
    const onSwitch = vi.fn().mockResolvedValue(nextSession)
    render(<OrganizationSwitcher session={session} switching={false} onSwitch={onSwitch} />)

    fireEvent.change(screen.getByRole('combobox', { name: 'Organisation active' }), {
      target: { value: 'membership-b' },
    })

    await waitFor(() => expect(onSwitch).toHaveBeenCalledWith('membership-b'))
    expect(onSwitch).not.toHaveBeenCalledWith('organization-b')
  })

  it('revient vers une route sûre après la commutation', async () => {
    window.history.replaceState({}, '', '/app/admin/users')
    const nextSession = { ...session, active_organization: memberships[1].organization }
    const onSwitch = vi.fn().mockResolvedValue(nextSession)
    render(<OrganizationSwitcher session={session} switching={false} onSwitch={onSwitch} />)

    fireEvent.change(screen.getByRole('combobox', { name: 'Organisation active' }), {
      target: { value: 'membership-b' },
    })

    await waitFor(() => expect(window.location.pathname).toBe('/app/search'))
  })

  it('conserve l’organisation courante et annonce une erreur contrôlée', async () => {
    const onSwitch = vi.fn().mockRejectedValue(new Error('Service indisponible.'))
    render(<OrganizationSwitcher session={session} switching={false} onSwitch={onSwitch} />)
    const select = screen.getByRole('combobox', { name: 'Organisation active' })

    fireEvent.change(select, { target: { value: 'membership-b' } })

    expect(await screen.findByRole('alert')).toHaveTextContent('Service indisponible.')
    expect(select).toHaveValue('membership-a')
  })

  it('désactive la commande pendant une commutation', () => {
    render(<OrganizationSwitcher session={session} switching onSwitch={vi.fn()} />)
    expect(screen.getByRole('combobox', { name: 'Organisation active' })).toBeDisabled()
    expect(screen.getByText('Changement d’organisation en cours…')).toBeInTheDocument()
  })
})
