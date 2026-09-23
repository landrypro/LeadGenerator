export const PUBLIC_LOCALE_STORAGE_KEY = 'marketteo.public-locale.v1'
export const PUBLIC_LOCALES = Object.freeze(['fr-CA', 'en-CA'])

export function resolvePublicLocale() {
  const stored = readStoredLocale()
  if (stored) return stored
  const languages = globalThis.navigator?.languages ?? [globalThis.navigator?.language]
  return languages.some((language) => String(language ?? '').toLowerCase().startsWith('en')) ? 'en-CA' : 'fr-CA'
}

export function savePublicLocale(locale) {
  const normalized = normalizeLocale(locale)
  if (!normalized) return resolvePublicLocale()
  try { globalThis.localStorage?.setItem(PUBLIC_LOCALE_STORAGE_KEY, normalized) } catch { /* Private browsing may deny storage. */ }
  return normalized
}

function readStoredLocale() {
  try { return normalizeLocale(globalThis.localStorage?.getItem(PUBLIC_LOCALE_STORAGE_KEY)) } catch { return null }
}

function normalizeLocale(locale) {
  return PUBLIC_LOCALES.includes(locale) ? locale : null
}
