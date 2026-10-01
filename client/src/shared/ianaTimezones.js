const PINNED_TIMEZONES = [
  'Africa/Douala',
  'America/Edmonton',
  'America/Halifax',
  'America/Montreal',
  'America/St_Johns',
  'America/Toronto',
  'America/Vancouver',
  'America/Winnipeg',
  'Asia/Dubai',
  'Europe/Paris',
  'UTC',
]

function collectTimezones() {
  try {
    const supported = typeof Intl.supportedValuesOf === 'function'
      ? Intl.supportedValuesOf('timeZone')
      : []
    return Object.freeze([...new Set([...PINNED_TIMEZONES, ...supported])].sort((left, right) => left.localeCompare(right)))
  } catch {
    return Object.freeze([...PINNED_TIMEZONES])
  }
}

export const IANA_TIMEZONES = collectTimezones()
