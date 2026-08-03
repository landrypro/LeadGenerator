import { useCallback } from 'react'

import { organizationApi } from '../api/organizationApi'
import { usePaginatedResource } from './usePaginatedResource'


const memberKey = (member) => member.membership_id


export function useMembers() {
  const resource = usePaginatedResource({
    fallbackMessage: 'Impossible de charger les membres.',
    keyOf: memberKey,
    loader: organizationApi.listMembers,
  })

  const reconcile = useCallback((member) => {
    resource.setItems((items) => items.map((current) => (
      current.membership_id === member.membership_id ? member : current
    )))
  }, [resource])

  return { ...resource, reconcile }
}
