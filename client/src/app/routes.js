import { AccountPage } from '../features/account/AccountPage'
import { PlatformAuditPage } from '../features/audit/PlatformAuditPage'
import { TenantAuditPage } from '../features/audit/TenantAuditPage'
import { PlaceSearchPage } from '../features/lead-search/LeadGeneratorPage'
import { OrganizationPage } from '../features/organizations/OrganizationPage'
import { MembersPage } from '../features/organizations/MembersPage'
import { PlatformOrganizationsPage } from '../features/platform/PlatformOrganizationsPage'
import { ProvidersAcquisitionsPage } from '../features/compliance/ProvidersAcquisitionsPage'
import { RetentionImportsPage } from '../features/retention/RetentionImportsPage'
import { ImportHistoryPage } from '../features/retention/ImportHistoryPage'
import { ExportsPage } from '../features/exports/ExportsPage'
import { CreateProspectPage } from '../features/prospects/CreateProspectPage'
import { ProspectDetailPage } from '../features/prospects/ProspectDetailPage'
import { ProspectsPage } from '../features/prospects/ProspectsPage'
import { PipelinePage } from '../features/prospects/PipelinePage'
import { TasksPage } from '../features/prospects/TasksPage'
import { OpportunitiesPage } from '../features/opportunities/OpportunitiesPage'
import { DashboardPage } from '../features/dashboard/DashboardPage'


export const CRM_PATHS = Object.freeze({
  home: '/',
  login: '/login',
  acceptInvitation: '/accept-invitation',
  search: '/app/search',
  dashboard: '/app/dashboard',
  prospects: '/app/prospects',
  prospectNew: '/app/prospects/new',
  prospectDetail: '/app/prospects/:prospectId',
  pipeline: '/app/pipeline',
  opportunities: '/app/opportunities',
  tasks: '/app/tasks',
  compliance: '/app/compliance/sources',
  retention: '/app/compliance/retention',
  importHistory: '/app/imports/history',
  exports: '/app/exports',
  account: '/app/account',
  organization: '/app/admin/organization',
  users: '/app/admin/users',
  platformOrganizations: '/app/platform/organizations',
  audit: '/app/audit',
  platformAudit: '/app/platform/audit',
})


const ROUTE_MESSAGES = Object.freeze({
  dashboard: Object.freeze({ 'fr-CA': Object.freeze({ label: 'Tableau de bord', title: 'Tableau de bord' }), 'en-CA': Object.freeze({ label: 'Dashboard', title: 'Dashboard' }) }),
  'retention-imports': Object.freeze({ 'fr-CA': Object.freeze({ label: 'Conservation et imports', title: 'Conservation des données' }), 'en-CA': Object.freeze({ label: 'Retention and imports', title: 'Data retention' }) }),
  'import-history': Object.freeze({ 'fr-CA': Object.freeze({ label: 'Historique des imports', title: 'Historique des imports' }), 'en-CA': Object.freeze({ label: 'Import history', title: 'Import history' }) }),
  exports: Object.freeze({ 'fr-CA': Object.freeze({ label: 'Exports', title: 'Exports CSV' }), 'en-CA': Object.freeze({ label: 'Exports', title: 'CSV exports' }) }),
  'compliance-sources': Object.freeze({ 'fr-CA': Object.freeze({ label: 'Sources et acquisitions', title: 'Fournisseurs et acquisitions' }), 'en-CA': Object.freeze({ label: 'Sources and acquisitions', title: 'Providers and acquisitions' }) }),
  pipeline: Object.freeze({ 'fr-CA': Object.freeze({ label: 'Pipeline', title: 'Pipeline commercial' }), 'en-CA': Object.freeze({ label: 'Pipeline', title: 'Sales pipeline' }) }),
  opportunities: Object.freeze({ 'fr-CA': Object.freeze({ label: 'Opportunités', title: 'Opportunités' }), 'en-CA': Object.freeze({ label: 'Opportunities', title: 'Opportunities' }) }),
  tasks: Object.freeze({ 'fr-CA': Object.freeze({ label: 'Mes tâches', title: 'Mes tâches' }), 'en-CA': Object.freeze({ label: 'My tasks', title: 'My tasks' }) }),
  prospects: Object.freeze({ 'fr-CA': Object.freeze({ label: 'Prospects', title: 'Prospects' }), 'en-CA': Object.freeze({ label: 'Prospects', title: 'Prospects' }) }),
  'prospect-new': Object.freeze({ 'fr-CA': Object.freeze({ label: 'Ajouter un prospect', title: 'Ajouter un prospect' }), 'en-CA': Object.freeze({ label: 'Add a prospect', title: 'Add a prospect' }) }),
  'prospect-detail': Object.freeze({ 'fr-CA': Object.freeze({ label: 'Fiche prospect', title: 'Fiche prospect' }), 'en-CA': Object.freeze({ label: 'Prospect record', title: 'Prospect record' }) }),
  'google-place-search': Object.freeze({ 'fr-CA': Object.freeze({ label: 'Recherche Google', title: 'Recherche d’établissements' }), 'en-CA': Object.freeze({ label: 'Google search', title: 'Business search' }) }),
  organization: Object.freeze({ 'fr-CA': Object.freeze({ label: 'Organisation', title: 'Organisation' }), 'en-CA': Object.freeze({ label: 'Organization', title: 'Organization' }) }),
  members: Object.freeze({ 'fr-CA': Object.freeze({ label: 'Membres', title: 'Membres et invitations' }), 'en-CA': Object.freeze({ label: 'Members', title: 'Members and invitations' }) }),
  'tenant-audit': Object.freeze({ 'fr-CA': Object.freeze({ label: 'Journal d’activité', title: 'Journal d’activité' }), 'en-CA': Object.freeze({ label: 'Activity log', title: 'Activity log' }) }),
  'platform-organizations': Object.freeze({ 'fr-CA': Object.freeze({ label: 'Plateforme', title: 'Organisations de la plateforme' }), 'en-CA': Object.freeze({ label: 'Platform', title: 'Platform organizations' }) }),
  'platform-audit': Object.freeze({ 'fr-CA': Object.freeze({ label: 'Audit plateforme', title: 'Audit plateforme' }), 'en-CA': Object.freeze({ label: 'Platform audit', title: 'Platform audit' }) }),
  account: Object.freeze({ 'fr-CA': Object.freeze({ label: 'Compte', title: 'Mon compte' }), 'en-CA': Object.freeze({ label: 'Account', title: 'My account' }) }),
})

// Seules les pages terminées sont enregistrées. Les chemins réservés ne sont
// rendus routables qu’avec leurs écrans, leurs capacités et leurs tests.
export const routes = Object.freeze([
  Object.freeze({
    id: 'dashboard', path: CRM_PATHS.dashboard, label: 'Tableau de bord', title: 'Tableau de bord',
    requiredCapability: 'dashboard:read:self', requiresActiveOrganization: true, Component: DashboardPage,
  }),
  Object.freeze({
    id: 'retention-imports', path: CRM_PATHS.retention, label: 'Conservation et imports', title: 'Conservation des données', requiredCapability: 'retention:read', requiresActiveOrganization: true, Component: RetentionImportsPage,
  }),
  Object.freeze({
    id: 'import-history', path: CRM_PATHS.importHistory, label: 'Historique des imports', title: 'Historique des imports', requiredCapability: 'imports:read', requiresActiveOrganization: true, Component: ImportHistoryPage,
  }),
  Object.freeze({
    id: 'exports', path: CRM_PATHS.exports, label: 'Exports', title: 'Exports CSV', requiredCapability: 'exports:create:self', requiresActiveOrganization: true, Component: ExportsPage,
  }),
  Object.freeze({
    id: 'compliance-sources',
    path: CRM_PATHS.compliance,
    label: 'Sources et acquisitions',
    title: 'Fournisseurs et acquisitions',
    requiredCapability: 'providers:read',
    requiresActiveOrganization: true,
    Component: ProvidersAcquisitionsPage,
  }),
  Object.freeze({
    id: 'pipeline',
    path: CRM_PATHS.pipeline,
    label: 'Pipeline',
    title: 'Pipeline commercial',
    requiredCapability: 'pipeline:read',
    requiresActiveOrganization: true,
    Component: PipelinePage,
  }),
  Object.freeze({
    id: 'opportunities',
    path: CRM_PATHS.opportunities,
    label: 'Opportunités',
    title: 'Opportunités',
    labels: Object.freeze({ 'fr-CA': 'Opportunités', 'en-CA': 'Opportunities' }),
    titles: Object.freeze({ 'fr-CA': 'Opportunités', 'en-CA': 'Opportunities' }),
    requiredCapability: 'opportunities:read',
    requiresActiveOrganization: true,
    Component: OpportunitiesPage,
  }),
  Object.freeze({
    id: 'tasks',
    path: CRM_PATHS.tasks,
    label: 'Mes tâches',
    title: 'Mes tâches',
    requiredCapability: 'tasks:read',
    requiresActiveOrganization: true,
    Component: TasksPage,
  }),
  Object.freeze({
    id: 'prospects',
    path: CRM_PATHS.prospects,
    label: 'Prospects',
    title: 'Prospects',
    requiredCapability: 'prospects:read',
    requiresActiveOrganization: true,
    Component: ProspectsPage,
  }),
  Object.freeze({
    id: 'prospect-new',
    path: CRM_PATHS.prospectNew,
    label: 'Ajouter un prospect',
    title: 'Ajouter un prospect',
    navigation: false,
    requiredCapability: 'prospects:create',
    requiresActiveOrganization: true,
    Component: CreateProspectPage,
  }),
  Object.freeze({
    id: 'prospect-detail',
    path: CRM_PATHS.prospectDetail,
    label: 'Fiche prospect',
    title: 'Fiche prospect',
    navigation: false,
    requiredCapability: 'prospects:read',
    requiresActiveOrganization: true,
    Component: ProspectDetailPage,
  }),
  Object.freeze({
    id: 'google-place-search',
    path: CRM_PATHS.search,
    label: 'Recherche Google',
    title: 'Recherche d’établissements',
    requiredCapability: 'google:search',
    requiresActiveOrganization: true,
    Component: PlaceSearchPage,
  }),
  Object.freeze({
    id: 'organization',
    path: CRM_PATHS.organization,
    label: 'Organisation',
    title: 'Organisation',
    requiredCapability: 'organization:read',
    requiresActiveOrganization: true,
    Component: OrganizationPage,
  }),
  Object.freeze({
    id: 'members',
    path: CRM_PATHS.users,
    label: 'Membres',
    title: 'Membres et invitations',
    requiredCapability: 'members:read',
    requiresActiveOrganization: true,
    Component: MembersPage,
  }),
  Object.freeze({
    id: 'tenant-audit',
    path: CRM_PATHS.audit,
    label: 'Journal d’activité',
    title: 'Journal d’activité',
    requiredCapability: 'audit:read',
    requiresActiveOrganization: true,
    Component: TenantAuditPage,
  }),
  Object.freeze({
    id: 'platform-organizations',
    path: CRM_PATHS.platformOrganizations,
    label: 'Plateforme',
    title: 'Organisations de la plateforme',
    requiredCapability: 'platform:organizations:read',
    requiresActiveOrganization: false,
    Component: PlatformOrganizationsPage,
  }),
  Object.freeze({
    id: 'platform-audit',
    path: CRM_PATHS.platformAudit,
    label: 'Audit plateforme',
    title: 'Audit plateforme',
    requiredCapability: 'platform:audit:read',
    requiresActiveOrganization: false,
    Component: PlatformAuditPage,
  }),
  Object.freeze({
    id: 'account',
    path: CRM_PATHS.account,
    label: 'Compte',
    title: 'Mon compte',
    requiredCapability: null,
    requiresActiveOrganization: false,
    Component: AccountPage,
  }),
])


export function findRoute(pathname) {
  const exact = routes.find((route) => route.path === pathname)
  if (exact) return exact
  for (const route of routes) {
    const names = []
    const pattern = route.path.replace(/:([A-Za-z][A-Za-z0-9_]*)/g, (_match, name) => {
      names.push(name)
      return '([^/]+)'
    })
    if (!names.length) continue
    const match = new RegExp(`^${pattern}$`).exec(pathname)
    if (!match) continue
    return { ...route, params: Object.fromEntries(names.map((name, index) => [name, decodeURIComponent(match[index + 1])])) }
  }
  return null
}


export function canAccessRoute(route, session) {
  if (!route || !session) return false
  if (route.requiresActiveOrganization && !session.active_organization) return false
  return !route.requiredCapability || session.capabilities.includes(route.requiredCapability)
}


export function navigationRoutes(session) {
  return routes.filter((route) => route.navigation !== false && canAccessRoute(route, session))
}


export function localizedRouteLabel(route, locale = 'fr-CA') {
  return ROUTE_MESSAGES[route?.id]?.[locale]?.label ?? route?.labels?.[locale] ?? route?.label ?? ''
}


export function localizedRouteTitle(route, locale = 'fr-CA') {
  return ROUTE_MESSAGES[route?.id]?.[locale]?.title ?? route?.titles?.[locale] ?? route?.title ?? ''
}


export function landingPath(session) {
  if (!session) return CRM_PATHS.login
  if (session.active_organization && session.capabilities.includes('google:search')) {
    return CRM_PATHS.search
  }
  if (session.active_organization && session.capabilities.includes('organization:read')) {
    return CRM_PATHS.organization
  }
  if (session.capabilities.includes('platform:organizations:read')) {
    return CRM_PATHS.platformOrganizations
  }
  return CRM_PATHS.account
}
