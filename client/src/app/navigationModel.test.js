import { describe, expect, it } from 'vitest'
import { navigationModel } from './navigationModel'
import { routes } from './routes'

describe('navigation hybride — capacités réelles', () => {
  const session = { active_organization: { id: 'a' }, capabilities: routes.map(route => route.requiredCapability).filter(Boolean) }
  it('classe chaque route visible une seule fois et conserve l’ordre quotidien', () => {
    const model = navigationModel(session)
    expect(model.direct.slice(0, 5).map(route => route.id)).toEqual(['dashboard', 'tasks', 'prospects', 'pipeline', 'opportunities'])
    expect(model.mobile.map(route => route.id)).toEqual(['dashboard', 'tasks', 'prospects', 'pipeline'])
    const ids = [...model.direct, ...model.groups.flatMap(group => group.routes), model.account].map(route => route.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids.sort()).toEqual(routes.filter(route => route.navigation !== false).map(route => route.id).sort())
    expect(ids).not.toContain('automation')
  })
  it('garde les groupes à un lien et filtre à partir des capacités, pas du rôle', () => {
    const model = navigationModel({ ...session, capabilities: ['google:search', 'imports:read'] }, 'en-CA')
    expect(model.direct).toEqual([])
    expect(model.mobile).toEqual([])
    expect(model.groups.map(group => [group.label, group.routes.map(route => route.id)])).toEqual([
      ['Acquisition', ['google-place-search']], ['Data and audit', ['import-history']],
    ])
  })
  it('distingue les deux capacités plateforme sans organisation', () => {
    const model = navigationModel({ active_organization: null, capabilities: ['platform:audit:read', 'google:search'] })
    expect(model.direct.map(route => route.id)).toEqual(['platform-audit'])
    expect(model.groups).toEqual([])
    expect(model.account.id).toBe('account')
    expect(navigationModel({ active_organization: null, capabilities: [] }).direct).toEqual([])
  })
})
