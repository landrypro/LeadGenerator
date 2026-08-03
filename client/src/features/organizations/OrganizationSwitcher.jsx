import { useEffect, useState } from 'react'

import { canAccessRoute, findRoute, landingPath } from '../../app/routes'
import { currentPath, navigate } from '../../app/navigation'
import { toUserMessage } from '../../shared/api/errors'


function activeMembershipId(session) {
  return session.memberships.find(
    (membership) => membership.organization.id === session.active_organization?.id,
  )?.id ?? ''
}


export function OrganizationSwitcher({ session, switching, onSwitch }) {
  const activeId = activeMembershipId(session)
  const [selectedMembershipId, setSelectedMembershipId] = useState(activeId)
  const [error, setError] = useState('')

  useEffect(() => {
    setSelectedMembershipId(activeId)
    setError('')
  }, [activeId])

  if (session.memberships.length < 2) {
    return session.active_organization && <span className="active-organization" title={session.active_organization.name}>
      {session.active_organization.name}
    </span>
  }

  async function changeOrganization(event) {
    const membershipId = event.target.value
    if (!membershipId || membershipId === activeId || switching) return
    setSelectedMembershipId(membershipId)
    setError('')
    try {
      const nextSession = await onSwitch(membershipId)
      if (!nextSession) return
      const route = findRoute(currentPath())
      if (!route || !canAccessRoute(route, nextSession)) {
        navigate(landingPath(nextSession), { replace: true })
      }
    } catch (switchError) {
      if (switchError?.name === 'AbortError') return
      setSelectedMembershipId(activeId)
      setError(toUserMessage(switchError, 'Le changement d’organisation a échoué.'))
    }
  }

  return <div className="organization-switcher">
    <label htmlFor="active-organization-select">Organisation active</label>
    <select
      id="active-organization-select"
      value={selectedMembershipId}
      onChange={changeOrganization}
      disabled={switching}
      aria-describedby={error ? 'organization-switch-error' : undefined}
    >
      {session.memberships.map((membership) => <option key={membership.id} value={membership.id}>
        {membership.organization.name}
      </option>)}
    </select>
    <span className="sr-only" aria-live="polite">{switching ? 'Changement d’organisation en cours…' : ''}</span>
    {error && <span id="organization-switch-error" className="organization-switch-error" role="alert">{error}</span>}
  </div>
}
