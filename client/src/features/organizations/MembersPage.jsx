import { useEffect, useRef, useState } from 'react'

import { UsersRound } from '../../icons'
import { navigate } from '../../app/navigation'
import { CRM_PATHS } from '../../app/routes'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { organizationApi } from './api/organizationApi'
import { InvitationPanel } from './components/InvitationPanel'
import { MemberEditor, ROLE_LABELS } from './components/MemberEditor'
import { useInvitations } from './hooks/useInvitations'
import { useMembers } from './hooks/useMembers'


const MEMBERS_MESSAGES = Object.freeze({
  'fr-CA': Object.freeze({ administration: 'Administration', title: 'Membres et invitations', description: 'Gérez les accès à l’organisation active selon les capacités de votre rôle.', accessAdmin: 'Administration des accès', members: 'Membres', invitations: 'Invitations', updated: 'Le membre a été mis à jour. Ses anciennes sessions ont été invalidées.', conflict: 'La version actuelle du membre a été chargée. La mutation n’a pas été rejouée.', lastAdmin: 'Cette action est impossible : l’organisation doit conserver un autre Administrateur actif.', updateError: 'Impossible de modifier ce membre.', loading: 'Chargement des membres…', membersOf: 'Membres de l’organisation', loaded: 'chargé', refresh: 'Actualiser', empty: 'Aucun membre accessible.', added: 'Ajouté', updatedAt: 'Mis à jour', edit: 'Modifier', loadingMore: 'Chargement…', loadMore: 'Charger la suite', statuses: Object.freeze({ active: 'Actif', disabled: 'Désactivé' }) }),
  'en-CA': Object.freeze({ administration: 'Administration', title: 'Members and invitations', description: 'Manage access to the active organization according to your role capabilities.', accessAdmin: 'Access administration', members: 'Members', invitations: 'Invitations', updated: 'The member was updated. Their previous sessions were invalidated.', conflict: 'The current member version was loaded. The mutation was not replayed.', lastAdmin: 'This action is unavailable: the organization must retain another active Administrator.', updateError: 'Unable to update this member.', loading: 'Loading members…', membersOf: 'Organization members', loaded: 'loaded', refresh: 'Refresh', empty: 'No accessible member.', added: 'Added', updatedAt: 'Updated', edit: 'Edit', loadingMore: 'Loading…', loadMore: 'Load more', statuses: Object.freeze({ active: 'Active', disabled: 'Disabled' }) }),
})


export function MembersPage({ createId, onSessionInvalidated, session }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = MEMBERS_MESSAGES[locale]
  const members = useMembers()
  const canManageMembers = session.capabilities.includes('members:manage')
  const canReadInvitations = session.capabilities.includes('invitations:read')
  const canManageInvitations = session.capabilities.includes('invitations:manage')
  const invitations = useInvitations(canReadInvitations)
  const [tab, setTab] = useState('members')
  const [selectedMemberId, setSelectedMemberId] = useState('')
  const [updating, setUpdating] = useState(false)
  const [mutationError, setMutationError] = useState('')
  const [conflictVersion, setConflictVersion] = useState('')
  const [success, setSuccess] = useState('')
  const mutationControllerRef = useRef(null)
  const mutationPendingRef = useRef(false)
  const mountedRef = useRef(true)
  const selectedMember = members.items.find((member) => member.membership_id === selectedMemberId)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      mutationControllerRef.current?.abort()
    }
  }, [])
  useEffect(() => {
    if (!canReadInvitations && tab === 'invitations') setTab('members')
  }, [canReadInvitations, tab])

  function navigateTabs(event) {
    const keys = { ArrowLeft: -1, ArrowRight: 1 }
    if (!(event.key in keys) && event.key !== 'Home' && event.key !== 'End') return
    event.preventDefault()
    const tabs = Array.from(event.currentTarget.querySelectorAll('[role="tab"]'))
    const currentIndex = tabs.indexOf(document.activeElement)
    const nextIndex = event.key === 'Home' ? 0 : event.key === 'End'
      ? tabs.length - 1 : (currentIndex + keys[event.key] + tabs.length) % tabs.length
    tabs[nextIndex]?.focus()
    tabs[nextIndex]?.click()
  }

  function selectMember(member) {
    setSelectedMemberId(member.membership_id)
    setMutationError('')
    setConflictVersion('')
    setSuccess('')
  }

  async function updateMember(changes) {
    if (!selectedMember || mutationPendingRef.current) return
    mutationPendingRef.current = true
    const controller = new AbortController()
    mutationControllerRef.current = controller
    setUpdating(true)
    setMutationError('')
    setConflictVersion('')
    setSuccess('')
    try {
      const updated = await organizationApi.updateMember(
        selectedMember.membership_id,
        { version: selectedMember.version, ...changes },
        controller.signal,
      )
      if (controller.signal.aborted || !mountedRef.current) return
      members.reconcile(updated)
      if (updated.user.id === session.user.id) {
        onSessionInvalidated?.()
        navigate(CRM_PATHS.login, { replace: true })
        return
      }
      setSuccess(copy.updated)
    } catch (updateError) {
      if (updateError?.name === 'AbortError' || !mountedRef.current) return
      if (updateError?.code === 'membership_version_conflict') {
        setConflictVersion(updateError.fields?.version ?? 'inconnue')
      } else if (updateError?.code === 'last_active_administrator') {
        setMutationError(copy.lastAdmin)
      } else {
        setMutationError(toUserMessage(updateError, copy.updateError))
      }
    } finally {
      mutationControllerRef.current = null
      mutationPendingRef.current = false
      if (mountedRef.current) setUpdating(false)
    }
  }

  async function reloadAfterConflict() {
    const page = await members.refresh()
    if (page) {
      setConflictVersion('')
      setMutationError('')
      setSuccess(copy.conflict)
    }
  }

  return <main className="administration-page members-page" aria-labelledby="members-page-title">
    <header className="administration-page-heading members-page-heading">
      <div className="administration-card-icon" aria-hidden="true"><UsersRound size={22} /></div>
      <div>
        <p className="eyebrow">{copy.administration}</p>
        <h1 id="members-page-title">{copy.title}</h1>
        <p>{copy.description}</p>
      </div>
    </header>

    {canReadInvitations && <div className="administration-tabs" role="tablist" aria-label={copy.accessAdmin} onKeyDown={navigateTabs}>
      <button id="members-tab" role="tab" aria-controls="members-panel" aria-selected={tab === 'members'} tabIndex={tab === 'members' ? 0 : -1} type="button" onClick={() => setTab('members')}>{copy.members}</button>
      <button id="invitations-tab" role="tab" aria-controls="invitations-panel" aria-selected={tab === 'invitations'} tabIndex={tab === 'invitations' ? 0 : -1} type="button" onClick={() => setTab('invitations')}>{copy.invitations}</button>
    </div>}

    <div id="members-panel" role="tabpanel" aria-labelledby={canReadInvitations ? 'members-tab' : undefined} aria-label={canReadInvitations ? undefined : copy.members} hidden={tab !== 'members'}>
      {success && <div className="success-banner" role="status"><span>{success}</span></div>}
      {selectedMember && canManageMembers && <MemberEditor
        member={selectedMember}
        busy={updating}
        error={mutationError}
        conflictVersion={conflictVersion}
        onCancel={() => setSelectedMemberId('')}
        onReload={reloadAfterConflict}
        onSubmit={updateMember}
        locale={locale}
      />}
      <MemberList members={members} canManage={canManageMembers} onSelect={selectMember} copy={copy} locale={locale} />
    </div>

    {canReadInvitations && <div id="invitations-panel" role="tabpanel" aria-labelledby="invitations-tab" hidden={tab !== 'invitations'}>
      <InvitationPanel canManage={canManageInvitations} createId={createId} invitations={invitations} locale={locale} />
    </div>}
  </main>
}


function MemberList({ canManage, copy, locale, members, onSelect }) {
  if (members.loading) return <div className="administration-loading">{copy.loading}</div>
  return <section className="administration-card resource-list-card" aria-labelledby="member-list-title">
    <div className="resource-list-heading">
      <div><h2 id="member-list-title">{copy.membersOf}</h2><p>{members.items.length} {copy.members.toLowerCase()} {copy.loaded}</p></div>
      <button className="text-button" type="button" onClick={members.refresh} disabled={members.refreshing}>{copy.refresh}</button>
    </div>
    {members.error && <ErrorBanner compact><span>{members.error}</span></ErrorBanner>}
    {!members.items.length ? <p className="administration-empty">{copy.empty}</p> : <ul className="member-list">
      {members.items.map((member) => <li key={member.membership_id}>
        <div className="member-identity">
          <span className="member-avatar" aria-hidden="true">{member.user.display_name.slice(0, 1).toUpperCase()}</span>
          <div><strong>{member.user.display_name}</strong><small>{member.user.email}</small></div>
        </div>
        <div className="member-metadata">
          <span>{ROLE_LABELS[member.role]?.[locale] ?? member.role}</span>
          <span className={`resource-status ${member.status}`}>{copy.statuses[member.status] ?? member.status}</span>
          <small>{copy.added} <time dateTime={member.created_at}>{formatDate(member.created_at, locale)}</time></small>
          <small>{copy.updatedAt} <time dateTime={member.updated_at}>{formatDate(member.updated_at, locale)}</time></small>
        </div>
        {canManage && <button className="secondary-button" type="button" onClick={() => onSelect(member)}>{copy.edit}</button>}
      </li>)}
    </ul>}
    {members.nextCursor && <button className="secondary-button load-more-button" type="button" onClick={members.loadMore} disabled={members.loadingMore}>
      {members.loadingMore ? copy.loadingMore : copy.loadMore}
    </button>}
  </section>
}


function formatDate(value, locale) {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
