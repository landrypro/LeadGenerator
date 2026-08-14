import { useCallback, useState } from 'react'

import { organizationApi } from '../api/organizationApi'
import { usePaginatedResource } from './usePaginatedResource'


const invitationKey = (invitation) => invitation.id


export function useInvitations(enabled) {
  const [state, setState] = useState('open')
  const loader = useCallback((cursor, limit, signal) => organizationApi.listInvitations(cursor, limit, signal, state), [state])
  const resource = usePaginatedResource({
    enabled,
    fallbackMessage: 'Impossible de charger les invitations.',
    keyOf: invitationKey,
    loader,
  })

  const upsert = useCallback((invitation, replacedId = '') => {
    resource.setItems((items) => {
      const remaining = items.filter((current) => current.id !== invitation.id && current.id !== replacedId)
      return [invitation, ...remaining]
    })
  }, [resource])

  const remove = useCallback((invitationId) => {
    resource.setItems((items) => items.filter((invitation) => invitation.id !== invitationId))
  }, [resource])

  return { ...resource, state, setState, upsert, remove }
}
