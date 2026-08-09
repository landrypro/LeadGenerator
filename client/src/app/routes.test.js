import { describe, expect, it } from 'vitest'

import {
  canAccessRoute, CRM_PATHS, findRoute, landingPath, navigationRoutes, routes,
} from './routes'


describe('routes CRM', () => {
  it('déclare les routes canoniques jusqu’à 2.4.3', () => {
    expect(CRM_PATHS).toEqual({
      home: '/',
      login: '/login',
      acceptInvitation: '/accept-invitation',
      search: '/app/search',
      account: '/app/account',
      organization: '/app/admin/organization',
      users: '/app/admin/users',
      platformOrganizations: '/app/platform/organizations',
      audit: '/app/audit',
      platformAudit: '/app/platform/audit',
    })
  })

  it('active les pages terminées jusqu’à la consultation d’audit', () => {
    expect(routes.map((route) => route.path)).toEqual([
      '/app/search',
      '/app/admin/organization',
      '/app/admin/users',
      '/app/audit',
      '/app/platform/organizations',
      '/app/platform/audit',
      '/app/account',
    ])
    expect(findRoute('/app/platform/organizations')?.requiredCapability).toBe('platform:organizations:read')
    expect(findRoute('/app/audit')?.requiredCapability).toBe('audit:read')
    expect(findRoute('/app/platform/audit')?.requiredCapability).toBe('platform:audit:read')
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

    const auditor = session({
      activeOrganization: { id: 'org-1', name: 'Entreprise' },
      capabilities: ['audit:read', 'platform:audit:read'],
    })
    expect(navigationRoutes(auditor).map((route) => route.id)).toEqual([
      'tenant-audit',
      'platform-audit',
      'account',
    ])
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
