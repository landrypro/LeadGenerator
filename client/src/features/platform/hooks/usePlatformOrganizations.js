import { useCallback } from 'react'

import { usePaginatedResource } from '../../organizations/hooks/usePaginatedResource'
import { platformApi } from '../api/platformApi'


const organizationKey = (view) => view.organization.id


export function usePlatformOrganizations() {
  const resource = usePaginatedResource({
    fallbackMessage: 'Impossible de charger les organisations de la plateforme.',
    keyOf: organizationKey,
    loader: platformApi.listOrganizations,
  })
  const upsert = useCallback((view) => resource.setItems((items) => {
    const found = items.some((current) => current.organization.id === view.organization.id)
    return found
      ? items.map((current) => current.organization.id === view.organization.id ? view : current)
      : [view, ...items]
  }), [resource])
  return { ...resource, upsert }
}
