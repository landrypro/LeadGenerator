import { AccountPage } from '../features/account/AccountPage'
import { PlaceSearchPage } from '../features/lead-search/LeadGeneratorPage'
import { OrganizationPage } from '../features/organizations/OrganizationPage'


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

// Seules les pages terminées sont enregistrées. Les chemins des incréments
// suivants restent réservés dans CRM_PATHS, mais ne sont ni routables ni
// affichés avant que leurs écrans et leurs tests soient livrés.
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
  return CRM_PATHS.account
}
