export const OPPORTUNITY_STAGES = [
  ['discovery', { 'fr-CA': 'Découverte', 'en-CA': 'Discovery' }],
  ['qualification', { 'fr-CA': 'Qualification', 'en-CA': 'Qualification' }],
  ['proposal', { 'fr-CA': 'Proposition', 'en-CA': 'Proposal' }],
  ['negotiation', { 'fr-CA': 'Négociation', 'en-CA': 'Negotiation' }],
  ['won', { 'fr-CA': 'Gagnée', 'en-CA': 'Won' }],
  ['lost', { 'fr-CA': 'Perdue', 'en-CA': 'Lost' }],
]

export const OPPORTUNITY_STAGE_LABELS = Object.fromEntries(OPPORTUNITY_STAGES)

export function stageLabel(code, locale = 'fr-CA') {
  return OPPORTUNITY_STAGE_LABELS[code]?.[locale] ?? OPPORTUNITY_STAGE_LABELS[code]?.['fr-CA'] ?? code
}

export function formatMoney(amount, currencyCode, locale = 'fr-CA') {
  const value = String(amount ?? '0').replace(/^(-?)(\d+)(?:\.(\d+))?$/, (_match, sign, integer, decimals = '') => {
    const group = locale === 'fr-CA' ? '\u202f' : ','
    const separator = locale === 'fr-CA' ? ',' : '.'
    const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, group)
    const trimmed = decimals.replace(/0+$/, '')
    return `${sign}${grouped}${trimmed ? `${separator}${trimmed}` : ''}`
  })
  return `${value} ${currencyCode}`
}

export function formatDate(value, locale = 'fr-CA') {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(new Date(`${value}T12:00:00Z`))
}
