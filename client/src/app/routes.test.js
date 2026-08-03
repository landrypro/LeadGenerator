import { describe, expect, it } from 'vitest'

import {
  canAccessRoute, CRM_PATHS, findRoute, landingPath, navigationRoutes, routes,
} from './routes'


describe('routes CRM', () => {
  it('déclare les sept routes canoniques de 2.3.5', () => {
    expect(CRM_PATHS).toEqual({
      home: '/',
      login: '/login',
      acceptInvitation: '/accept-invitation',
      search: '/app/search',
      account: '/app/account',
      organization: '/app/admin/organization',
      users: '/app/admin/users',
      platformOrganizations: '/app/platform/organizations',
    })
  })

  it('active les pages terminées jusqu’au lot D', () => {
    expect(routes.map((route) => route.path)).toEqual([
      '/app/search',
      '/app/admin/organization',
      '/app/admin/users',
      '/app/platform/organizations',
      '/app/account',
    ])
    expect(findRoute('/app/platform/organizations')?.requiredCapability).toBe('platform:organizations:read')
  })

  it('filtre les routes selon l’organisation active et les capacités', () => {
    const accountOnly = session({ activeOrganization: null })
    expect(navigationRoutes(accountOnly).map((route) => route.id)).toEqual(['account'])

    const tenant = session({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['google:search', 'organization:read', 'members:read'],
    })
    expect(navigationRoutes(tenant).map((route) => route.id)).toEqual([
      'google-place-search',
      'organization',
      'members',
      'account',
    ])
    expect(canAccessRoute(findRoute('/app/search'), tenant)).toBe(true)
  })

  it('choisit une destination sûre selon le contexte courant', () => {
    expect(landingPath(null)).toBe('/login')
    expect(landingPath(session({ activeOrganization: null }))).toBe('/app/account')
    expect(landingPath(session({
      activeOrganization: null,
      capabilities: ['platform:organizations:read'],
    }))).toBe('/app/platform/organizations')
    expect(landingPath(session({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['organization:read'],
    }))).toBe('/app/admin/organization')
    expect(landingPath(session({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['google:search'],
    }))).toBe('/app/search')
    expect(landingPath(session({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['organization:read', 'platform:organizations:read'],
    }))).toBe('/app/admin/organization')
  })
})


function session({ activeOrganization, capabilities = [] }) {
  return { active_organization: activeOrganization, capabilities }
}
