import { afterEach, describe, expect, it } from 'vitest'

import { PUBLIC_LOCALE_STORAGE_KEY, resolvePublicLocale, savePublicLocale } from './publicLocale'

describe('public locale', () => {
  afterEach(() => window.localStorage.clear())

  it('uses the stored locale before the browser locale', () => {
    window.localStorage.setItem(PUBLIC_LOCALE_STORAGE_KEY, 'fr-CA')
    expect(resolvePublicLocale()).toBe('fr-CA')
  })

  it('stores only a recognized locale', () => {
    expect(savePublicLocale('en-CA')).toBe('en-CA')
    expect(window.localStorage.getItem(PUBLIC_LOCALE_STORAGE_KEY)).toBe('en-CA')
    expect(savePublicLocale('invalid')).not.toBe('invalid')
  })
})
