import { AccountPage } from '../features/account/AccountPage'
import { PlatformAuditPage } from '../features/audit/PlatformAuditPage'
import { TenantAuditPage } from '../features/audit/TenantAuditPage'
import { PlaceSearchPage } from '../features/lead-search/LeadGeneratorPage'
import { OrganizationPage } from '../features/organizations/OrganizationPage'
import { MembersPage } from '../features/organizations/MembersPage'
import { PlatformOrganizationsPage } from '../features/platform/PlatformOrganizationsPage'
import { ProvidersAcquisitionsPage } from '../features/compliance/ProvidersAcquisitionsPage'
import { RetentionImportsPage } from '../features/retention/RetentionImportsPage'
import { CreateProspectPage } from '../features/prospects/CreateProspectPage'
import { ProspectDetailPage } from '../features/prospects/ProspectDetailPage'
import { ProspectsPage } from '../features/prospects/ProspectsPage'
import { PipelinePage } from '../features/prospects/PipelinePage'
import { TasksPage } from '../features/prospects/TasksPage'


export const CRM_PATHS = Object.freeze({
  home: '/',
  login: '/login',
  acceptInvitation: '/accept-invitation',
  search: '/app/search',
  prospects: '/app/prospects',
  prospectNew: '/app/prospects/new',
  prospectDetail: '/app/prospects/:prospectId',
  pipeline: '/app/pipeline',
  tasks: '/app/tasks',
  compliance: '/app/compliance/sources',
  retention: '/app/compliance/retention',
  account: '/app/account',
  organization: '/app/admin/organization',
  users: '/app/admin/users',
  platformOrganizations: '/app/platform/organizations',
  audit: '/app/audit',
  platformAudit: '/app/platform/audit',
})

// Seules les pages terminées sont enregistrées. Les chemins réservés ne sont
// rendus routables qu’avec leurs écrans, leurs capacités et leurs tests.
export const routes = Object.freeze([
  Object.freeze({
    id: 'retention-imports', path: CRM_PATHS.retention, label: 'Conservation et imports', title: 'Conservation des données', requiredCapability: 'retention:read', requiresActiveOrganization: true, Component: RetentionImportsPage,
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
