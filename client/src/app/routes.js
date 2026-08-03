import { AccountPage } from '../features/account/AccountPage'
import { PlaceSearchPage } from '../features/lead-search/LeadGeneratorPage'
import { OrganizationPage } from '../features/organizations/OrganizationPage'
import { MembersPage } from '../features/organizations/MembersPage'
import { PlatformOrganizationsPage } from '../features/platform/PlatformOrganizationsPage'


export const CRM_PATHS = Object.freeze({
  home: '/',
  login: '/login',
  acceptInvitation: '/accept-invitation',
  search: '/app/search',
  account: '/app/account',
  organization: '/app/admin/organization',
  users: '/app/admin/users',
  platformOrganizations: '/app/platform/organizations',
})

// Seules les pages terminées sont enregistrées. Les chemins réservés ne sont
// rendus routables qu’avec leurs écrans, leurs capacités et leurs tests.
export const routes = Object.freeze([
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
    id: 'platform-organizations',
    path: CRM_PATHS.platformOrganizations,
    label: 'Plateforme',
    title: 'Organisations de la plateforme',
    requiredCapability: 'platform:organizations:read',
    requiresActiveOrganization: false,
    Component: PlatformOrganizationsPage,
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
  return routes.find((route) => route.path === pathname) ?? null
}


export function canAccessRoute(route, session) {
  if (!route || !session) return false
  if (route.requiresActiveOrganization && !session.active_organization) return false
  return !route.requiredCapability || session.capabilities.includes(route.requiredCapability)
}


export function navigationRoutes(session) {
  return routes.filter((route) => canAccessRoute(route, session))
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
