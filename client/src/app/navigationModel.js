import { navigationRoutes } from './routes'

// Automation is reserved after dashboard, but has no route until product activation.
const directIds = ['dashboard', 'tasks', 'prospects', 'pipeline', 'opportunities', 'platform-organizations', 'platform-audit']
const mobileIds = ['dashboard', 'tasks', 'prospects', 'pipeline']
const groups = [
  { id: 'acquisition', labels: { 'fr-CA': 'Acquisition', 'en-CA': 'Acquisition' }, ids: ['google-place-search', 'compliance-sources'] },
  { id: 'data', labels: { 'fr-CA': 'Données et audit', 'en-CA': 'Data and audit' }, ids: ['usage', 'retention-imports', 'import-history', 'exports', 'tenant-audit'] },
  { id: 'administration', labels: { 'fr-CA': 'Administration', 'en-CA': 'Administration' }, ids: ['organization', 'members'] },
]

export function navigationModel(session, locale = 'fr-CA') {
  const available = new Map(navigationRoutes(session).map(route => [route.id, route]))
  const resolve = ids => ids.map(id => available.get(id)).filter(Boolean)
  return {
    direct: resolve(directIds),
    mobile: resolve(mobileIds),
    groups: groups.map(group => ({ id: group.id, label: group.labels[locale] ?? group.labels['fr-CA'], routes: resolve(group.ids) })).filter(group => group.routes.length),
    account: available.get('account'),
  }
}

export function navigationRouteId(route) {
  return ['prospect-new', 'prospect-detail'].includes(route?.id) ? 'prospects' : route?.id
}

export function navigationLabel(route, locale) {
  const labels = {
    usage: ['Quotas et usage', 'Quotas and usage'],
    exports: ['Exports CSV', 'CSV exports'],
    'google-place-search': ['Recherche d’établissements', 'Business search'],
  }
  return labels[route.id]?.[locale === 'en-CA' ? 1 : 0]
}
