export const FALLBACK_TIMEZONE = 'America/Toronto'


export function resolveDefaultTimezone(resolver = () => Intl.DateTimeFormat().resolvedOptions().timeZone) {
  try {
    const timezone = resolver()
    if (!timezone) return FALLBACK_TIMEZONE
    new Intl.DateTimeFormat('fr-CA', { timeZone: timezone }).format()
    return timezone
  } catch {
    return FALLBACK_TIMEZONE
  }
}
