import { describe, expect, it } from 'vitest'

import { CRM_PATHS, routes } from './routes'


describe('routes CRM', () => {
  it('conserve la page actuelle et réserve les neuf modules V1', () => {
    expect(routes[0].path).toBe('/')
    expect(CRM_PATHS).toMatchObject({
      dashboard: '/dashboard',
      prospects: '/prospects',
      pipeline: '/pipeline',
      activities: '/activities',
      actions: '/actions',
      opportunities: '/opportunities',
      compliance: '/compliance',
      importsExports: '/imports-exports',
      administration: '/administration',
    })
  })
})
