import { useEffect, useRef, useState } from 'react'

import { createRequestId } from '../../../shared/ids/requestId'
import { toUserMessage } from '../../../shared/api/errors'
import { organizationApi } from '../api/organizationApi'
import { ConfirmationDialog } from './ConfirmationDialog'
import { ROLE_LABELS } from './MemberEditor'


const STATE_LABELS = { active: 'Active', expired: 'Expirée', accepted: 'Acceptée', revoked: 'Révoquée' }
const DELIVERY_LABELS = { pending: 'En attente', sent: 'Envoyée', failed: 'Échec de livraison' }


export function InvitationPanel({ canManage = true, createId = createRequestId, invitations }) {
  const [form, setForm] = useState({ email: '', role: 'sales' })
  const [creationIntent, setCreationIntent] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [busyInvitationIds, setBusyInvitationIds] = useState(() => new Set())
  const [resendIntents, setResendIntents] = useState({})
  const [revoking, setRevoking] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const controllersRef = useRef(new Set())
  const mountedRef = useRef(true)
  const creationPendingRef = useRef(false)
  const busyInvitationIdsRef = useRef(new Set())

  useEffect(() => {
    const controllers = controllersRef.current
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      controllers.forEach((controller) => controller.abort())
      controllers.clear()
    }
  }, [])

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
    setCreationIntent(null)
    setError('')
    setSuccess('')
  }

  async function createInvitation(event) {
    event.preventDefault()
    if (creationPendingRef.current || !form.email.trim()) return
    creationPendingRef.current = true
    const intent = creationIntent ?? {
      id: createId(),
      payload: { email: form.email.trim(), role: form.role },
    }
    if (!creationIntent) setCreationIntent(intent)
    const controller = trackController(controllersRef)
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const invitation = await organizationApi.createInvitation({
        ...intent.payload,
        invitation_request_id: intent.id,
      }, controller.signal)
      if (controller.signal.aborted || !mountedRef.current) return
      invitations.upsert(invitation)
      setForm({ email: '', role: 'sales' })
      setCreationIntent(null)
      setSuccess(invitation.delivery_status === 'failed'
        ? 'L’invitation existe, mais sa livraison a échoué. Vous pouvez la renvoyer.'
        : 'L’invitation a été créée et confiée au service de livraison.')
    } catch (invitationError) {
      if (invitationError?.name !== 'AbortError' && mountedRef.current) setError(invitationErrorMessage(invitationError))
    } finally {
      releaseController(controllersRef, controller)
      creationPendingRef.current = false
      if (mountedRef.current) setSubmitting(false)
    }
  }

  async function resend(invitation) {
    if (busyInvitationIdsRef.current.has(invitation.id)) return
    const requestId = resendIntents[invitation.id] ?? createId()
    if (!resendIntents[invitation.id]) {
      setResendIntents((current) => ({ ...current, [invitation.id]: requestId }))
    }
    const controller = trackController(controllersRef)
    setInvitationBusy(busyInvitationIdsRef, setBusyInvitationIds, invitation.id, true)
    setError('')
    setSuccess('')
    try {
      const replacement = await organizationApi.resendInvitation(
        invitation.id,
        { resend_request_id: requestId },
        controller.signal,
      )
      if (controller.signal.aborted || !mountedRef.current) return
      invitations.upsert(replacement, invitation.id)
      setResendIntents((current) => withoutKey(current, invitation.id))
      setSuccess('Un nouveau lien d’invitation a été généré et confié au service de livraison.')
    } catch (resendError) {
      if (resendError?.name !== 'AbortError' && mountedRef.current) setError(invitationErrorMessage(resendError))
    } finally {
      releaseController(controllersRef, controller)
      setInvitationBusy(busyInvitationIdsRef, setBusyInvitationIds, invitation.id, false, mountedRef.current)
    }
  }

  async function revoke() {
    if (!revoking || busyInvitationIdsRef.current.has(revoking.id)) return
    const invitation = revoking
    const controller = trackController(controllersRef)
    setInvitationBusy(busyInvitationIdsRef, setBusyInvitationIds, invitation.id, true)
    setError('')
    setSuccess('')
    try {
      await organizationApi.revokeInvitation(invitation.id, controller.signal)
      if (controller.signal.aborted || !mountedRef.current) return
      invitations.remove(invitation.id)
      setRevoking(null)
      setSuccess('L’invitation a été révoquée.')
    } catch (revokeError) {
      if (revokeError?.name !== 'AbortError' && mountedRef.current) setError(invitationErrorMessage(revokeError))
    } finally {
      releaseController(controllersRef, controller)
      setInvitationBusy(busyInvitationIdsRef, setBusyInvitationIds, invitation.id, false, mountedRef.current)
    }
  }

  return <div className="invitation-panel">
    {canManage && <section className="administration-card invitation-form-card" aria-labelledby="invite-member-title">
      <h2 id="invite-member-title">Inviter une personne</h2>
      <p>Le lien est envoyé par le service configuré. Aucun jeton n’est affiché dans le navigateur.</p>
      <form className="invitation-form" onSubmit={createInvitation}>
        <label htmlFor="invitation-email">Adresse courriel</label>
        <input id="invitation-email" type="email" autoComplete="email" value={form.email} onChange={(event) => updateForm('email', event.target.value)} maxLength="254" required />
        <label htmlFor="invitation-role">Rôle proposé</label>
        <select id="invitation-role" value={form.role} onChange={(event) => updateForm('role', event.target.value)}>
          {Object.entries(ROLE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <button className="primary-button" type="submit" disabled={submitting || !form.email.trim()}>
          {submitting ? 'Création…' : 'Créer l’invitation'}
        </button>
      </form>
    </section>}

    {error && <div className="error-banner" role="alert"><span>{error}</span></div>}
    {success && <div className="success-banner" role="status"><span>{success}</span></div>}

    <InvitationList
      invitations={invitations}
      canManage={canManage}
      busyInvitationIds={busyInvitationIds}
      onResend={resend}
      onRevoke={setRevoking}
    />

    {revoking && <ConfirmationDialog
      title="Révoquer cette invitation ?"
      confirmLabel="Révoquer l’invitation"
      busy={busyInvitationIds.has(revoking.id)}
      onCancel={() => setRevoking(null)}
      onConfirm={revoke}
    >
      <p>Le lien envoyé à <strong>{revoking.recipient_email}</strong> cessera immédiatement d’être utilisable.</p>
    </ConfirmationDialog>}
  </div>
}


function InvitationList({ busyInvitationIds, canManage, invitations, onResend, onRevoke }) {
  if (invitations.loading) return <div className="administration-loading">Chargement des invitations…</div>
  return <section className="administration-card resource-list-card" aria-labelledby="invitation-list-title">
    <div className="resource-list-heading">
      <div><h2 id="invitation-list-title">Invitations actionnables</h2><p>Cette liste ne constitue pas un historique complet.</p></div>
      <button className="text-button" type="button" onClick={invitations.refresh} disabled={invitations.refreshing}>Actualiser</button>
    </div>
    {invitations.error && <div className="error-banner compact" role="alert"><span>{invitations.error}</span></div>}
    {!invitations.items.length ? <p className="administration-empty">Aucune invitation en attente ou expirée.</p> : <ul className="invitation-list">
      {invitations.items.map((invitation) => <li key={invitation.id}>
        <div className="invitation-identity">
          <strong>{invitation.recipient_email}</strong>
          <span>{ROLE_LABELS[invitation.role] ?? invitation.role}</span>
        </div>
        <div className="invitation-state">
          <span className={`resource-status ${invitation.state}`}>{STATE_LABELS[invitation.state] ?? invitation.state}</span>
          <span className={`delivery-status ${invitation.delivery_status}`}>{DELIVERY_LABELS[invitation.delivery_status] ?? invitation.delivery_status}</span>
          <small>Expire le <time dateTime={invitation.expires_at}>{formatDate(invitation.expires_at)}</time></small>
        </div>
        {canManage && <div className="resource-actions">
          <button className="secondary-button" type="button" onClick={() => onResend(invitation)} disabled={busyInvitationIds.has(invitation.id)}>
            {busyInvitationIds.has(invitation.id) ? 'Traitement…' : 'Renvoyer'}
          </button>
          <button className="danger-link" type="button" onClick={() => onRevoke(invitation)} disabled={busyInvitationIds.has(invitation.id)}>Révoquer</button>
        </div>}
      </li>)}
    </ul>}
    {invitations.nextCursor && <button className="secondary-button load-more-button" type="button" onClick={invitations.loadMore} disabled={invitations.loadingMore}>
      {invitations.loadingMore ? 'Chargement…' : 'Charger la suite'}
    </button>}
  </section>
}


function invitationErrorMessage(error) {
  if (error?.code === 'invitation_outcome_unknown') {
    return 'Le résultat est incertain. Réessayez sans modifier le formulaire afin de conserver la même intention.'
  }
  if (error?.code === 'invitation_rate_limited' && error.retryAfter) {
    return `Trop de renvois. Réessayez dans ${error.retryAfter} secondes.`
  }
  return toUserMessage(error, 'L’opération sur l’invitation a échoué.')
}


function formatDate(value) {
  return new Intl.DateTimeFormat('fr-CA', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}


function trackController(reference) {
  const controller = new AbortController()
  reference.current.add(controller)
  return controller
}


function releaseController(reference, controller) {
  reference.current.delete(controller)
}


function withoutKey(object, key) {
  const next = { ...object }
  delete next[key]
  return next
}


function setInvitationBusy(reference, setter, invitationId, busy, render = true) {
  const next = new Set(reference.current)
  if (busy) next.add(invitationId)
  else next.delete(invitationId)
  reference.current = next
  if (render) setter(next)
}
