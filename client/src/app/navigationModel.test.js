import { describe, expect, it } from 'vitest'
import { navigationModel, navigationRouteId } from './navigationModel'
import { routes } from './routes'

describe('navigation hybride — capacités réelles', () => {
  const session = { active_organization: { id: 'a' }, capabilities: routes.map(route => route.requiredCapability).filter(Boolean) }
  it('classe chaque route visible une seule fois et conserve l’ordre quotidien', () => {
    const model = navigationModel(session)
    expect(model.direct.slice(0, 6).map(route => route.id)).toEqual(['dashboard', 'automation', 'tasks', 'prospects', 'pipeline', 'opportunities'])
    expect(model.mobile.map(route => route.id)).toEqual(['dashboard', 'tasks', 'prospects', 'pipeline'])
    const ids = [...model.direct, ...model.groups.flatMap(group => group.routes), model.account].map(route => route.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids.sort()).toEqual(routes.filter(route => route.navigation !== false).map(route => route.id).sort())
    expect(ids).toContain('automation')
    expect(model.groups.find(group => group.id === 'administration').routes.map(route => route.id)).toContain('automation-settings')
  })
  it('garde les groupes à un lien et filtre à partir des capacités, pas du rôle', () => {
    const model = navigationModel({ ...session, capabilities: ['google:search', 'imports:read'] }, 'en-CA')
    expect(model.direct).toEqual([])
    expect(model.mobile).toEqual([])
    expect(model.groups.map(group => [group.label, group.routes.map(route => route.id)])).toEqual([
      ['Acquisition', ['google-place-search']], ['Data and audit', ['import-history']],
    ])
    expect(model.groups.flatMap(group => group.routes.map(route => route.id))).not.toContain('automation-settings')
  })
  it('distingue les deux capacités plateforme sans organisation', () => {
    const model = navigationModel({ active_organization: null, capabilities: ['platform:audit:read', 'google:search'] })
    expect(model.direct.map(route => route.id)).toEqual(['platform-audit'])
    expect(model.groups).toEqual([])
    expect(model.account.id).toBe('account')
    expect(navigationModel({ active_organization: null, capabilities: [] }).direct).toEqual([])
  })
  it('conserve Automatisation active dans la navigation globale depuis ses sous-pages', () => {
    expect(navigationRouteId({ id: 'automation-playbooks' })).toBe('automation')
    expect(navigationRouteId({ id: 'automation-exceptions' })).toBe('automation')
  })
  it('retire l’entrée globale quand l’organisation suspend Automation mais conserve le réglage admin', () => {
    const model = navigationModel({
      ...session,
      automation_available: false,
    })
    expect(model.direct.map((route) => route.id)).not.toContain('automation')
    expect(model.groups.find((group) => group.id === 'administration').routes.map((route) => route.id)).toContain('automation-settings')
  })
})
