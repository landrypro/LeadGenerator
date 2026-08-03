import { describe, expect, it } from 'vitest'

import { FALLBACK_TIMEZONE, resolveDefaultTimezone } from './defaultTimezone'


describe('resolveDefaultTimezone', () => {
  it('conserve un fuseau IANA valide', () => expect(resolveDefaultTimezone(() => 'America/Vancouver')).toBe('America/Vancouver'))
  it('retombe sur Toronto si le navigateur ne fournit rien', () => expect(resolveDefaultTimezone(() => '')).toBe(FALLBACK_TIMEZONE))
  it('retombe sur Toronto si le fuseau est invalide', () => expect(resolveDefaultTimezone(() => 'Fuseau/Invalide')).toBe(FALLBACK_TIMEZONE))
})
