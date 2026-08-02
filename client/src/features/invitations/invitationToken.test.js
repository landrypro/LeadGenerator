import { describe, expect, it, vi } from 'vitest'

import { extractInvitationToken } from './invitationToken'


function browser(hash) {
  return {
    location: { hash, pathname: '/accept-invitation', search: '?source=email' },
    history: { state: { preserved: true }, replaceState: vi.fn() },
  }
}


describe('extractInvitationToken', () => {
  it('retire le fragment avant de retourner le jeton valide en mémoire', () => {
    const target = browser(`#token=${'A'.repeat(43)}`)

    const token = extractInvitationToken(target)

    expect(token).toBe('A'.repeat(43))
    expect(target.history.replaceState).toHaveBeenCalledWith(
      { preserved: true },
      '',
      '/accept-invitation?source=email',
    )
  })

  it('retire aussi un fragment mal formé et ne retourne aucun jeton', () => {
    const target = browser('#token=secret-invalide&debug=true')

    expect(extractInvitationToken(target)).toBe('')
    expect(target.history.replaceState).toHaveBeenCalledTimes(1)
  })

  it('ne modifie pas l’historique en l’absence de fragment', () => {
    const target = browser('')

    expect(extractInvitationToken(target)).toBe('')
    expect(target.history.replaceState).not.toHaveBeenCalled()
  })
})
