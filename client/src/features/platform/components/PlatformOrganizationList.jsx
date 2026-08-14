import { useEffect, useRef, useState } from 'react'

import { toUserMessage } from '../../../shared/api/errors'
import { createRequestId } from '../../../shared/ids/requestId'
import { ErrorBanner } from '../../../shared/ui/Feedback'
import { ConfirmationDialog } from '../../organizations/components/ConfirmationDialog'
import { platformApi } from '../api/platformApi'


const ORGANIZATION_LABELS = { active: 'Active', provisioning: 'Activation en cours', suspended: 'Suspendue' }
const INVITATION_LABELS = { active: 'Active', expired: 'Expirée', accepted: 'Acceptée', revoked: 'Révoquée' }
const DELIVERY_LABELS = { pending: 'En attente', sent: 'Envoyée', failed: 'Échec de livraison' }
const REASON_LABELS = {
  customer_request: 'Demande client',
  billing: 'Facturation',
  security: 'Sécurité',
  compliance: 'Conformité',
  administrative: 'Administration',
  other: 'Autre',
}


export function PlatformOrganizationList({ canManage, canManageStatus = false, createId = createRequestId, onReconciled, organizations }) {
  const [busyIds, setBusyIds] = useState(() => new Set())
  const [resendIntents, setResendIntents] = useState({})
  const [blockedResends, setBlockedResends] = useState(() => new Set())
  const [revoking, setRevoking] = useState(null)
  const [statusIntent, setStatusIntent] = useState(null)
  const [message, setMessage] = useState({ type: '', text: '' })
  const busyRef = useRef(new Set())
  const controllersRef = useRef(new Set())
  const mountedRef = useRef(true)

  useEffect(() => {
    const controllers = controllersRef.current
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      controllers.forEach((controller) => controller.abort())
      controllers.clear()
    }
  }, [])

  async function resend(view) {
    const organizationId = view.organization.id
    if (busyRef.current.has(organizationId) || blockedResends.has(organizationId)) return
    const requestId = resendIntents[organizationId] ?? createId()
    if (!resendIntents[organizationId]) setResendIntents((current) => ({ ...current, [organizationId]: requestId }))
    const controller = track(controllersRef)
    setBusy(busyRef, setBusyIds, organizationId, true)
    setMessage({ type: '', text: '' })
    try {
      const updated = await platformApi.resendInitialInvitation(organizationId, { resend_request_id: requestId }, controller.signal)
      if (controller.signal.aborted || !mountedRef.current) return
      onReconciled(updated)
      setResendIntents((current) => withoutKey(current, organizationId))
      setBlockedResends((current) => withoutSetValue(current, organizationId))
      setMessage({ type: 'success', text: `Une nouvelle invitation initiale a été envoyée pour ${updated.organization.name}. L’ancien lien est invalide.` })
    } catch (error) {
      if (error?.name === 'AbortError' || !mountedRef.current) return
      if (error?.code === 'idempotency_key_reused') setBlockedResends((current) => new Set(current).add(organizationId))
      setMessage({ type: 'error', text: actionErrorMessage(error) })
    } finally {
      release(controllersRef, controller)
      setBusy(busyRef, setBusyIds, organizationId, false, mountedRef.current)
    }
  }

  function abandonResend(organizationId) {
    setResendIntents((current) => withoutKey(current, organizationId))
    setBlockedResends((current) => withoutSetValue(current, organizationId))
    setMessage({ type: 'status', text: 'Une nouvelle intention de renvoi sera créée à la prochaine action.' })
  }

  async function revoke() {
    if (!revoking || busyRef.current.has(revoking.organization.id)) return
    const organizationId = revoking.organization.id
    const controller = track(controllersRef)
    setBusy(busyRef, setBusyIds, organizationId, true)
    setMessage({ type: '', text: '' })
    try {
      const updated = await platformApi.revokeInitialInvitation(organizationId, controller.signal)
      if (controller.signal.aborted || !mountedRef.current) return
      onReconciled(updated)
      setRevoking(null)
      setMessage({ type: 'success', text: `L’invitation initiale de ${updated.organization.name} a été révoquée.` })
    } catch (error) {
      if (error?.name !== 'AbortError' && mountedRef.current) setMessage({ type: 'error', text: actionErrorMessage(error) })
    } finally {
      release(controllersRef, controller)
      setBusy(busyRef, setBusyIds, organizationId, false, mountedRef.current)
    }
  }

  async function changeStatus(event) {
    event.preventDefault()
    if (!statusIntent || busyRef.current.has(statusIntent.view.organization.id)) return
    const organizationId = statusIntent.view.organization.id
    const controller = track(controllersRef)
    setBusy(busyRef, setBusyIds, organizationId, true)
    setMessage({ type: '', text: '' })
    try {
      const payload = {
        operation_id: statusIntent.operationId,
        version: statusIntent.view.organization.version,
        reason_code: statusIntent.reasonCode,
        external_reference: statusIntent.externalReference.trim() || null,
      }
      const updated = statusIntent.operation === 'suspend'
        ? await platformApi.suspendOrganization(organizationId, payload, controller.signal)
        : await platformApi.reactivateOrganization(organizationId, payload, controller.signal)
      if (controller.signal.aborted || !mountedRef.current) return
      onReconciled(updated)
      setStatusIntent(null)
      setMessage({ type: 'success', text: `${updated.organization.name} est maintenant ${ORGANIZATION_LABELS[updated.organization.status]?.toLowerCase() ?? updated.organization.status}.` })
    } catch (error) {
      if (error?.name !== 'AbortError' && mountedRef.current) setMessage({ type: 'error', text: actionErrorMessage(error) })
    } finally {
      release(controllersRef, controller)
      setBusy(busyRef, setBusyIds, organizationId, false, mountedRef.current)
    }
  }

  function openStatusIntent(view, operation) {
    setStatusIntent({ view, operation, operationId: createId(), reasonCode: 'administrative', externalReference: '' })
  }

  if (organizations.loading) return <div className="administration-loading">Chargement des organisations…</div>
  return <>
    {message.text && (message.type === 'error'
      ? <ErrorBanner><span>{message.text}</span></ErrorBanner>
      : <div className="success-banner" role="status"><span>{message.text}</span></div>)}
    <OrganizationList organizations={organizations} canManage={canManage} canManageStatus={canManageStatus} busyIds={busyIds} blockedResends={blockedResends} onAbandonResend={abandonResend} onResend={resend} onRevoke={setRevoking} onStatusChange={openStatusIntent} />
    {revoking && <ConfirmationDialog title="Révoquer cette invitation initiale ?" confirmLabel="Révoquer l’invitation" busy={busyIds.has(revoking.organization.id)} onCancel={() => setRevoking(null)} onConfirm={revoke}>
      <p>Le lien envoyé à <strong>{revoking.first_invitation.recipient_email}</strong> cessera immédiatement d’être utilisable. L’organisation restera en cours d’activation.</p>
    </ConfirmationDialog>}
    {statusIntent && <ConfirmationDialog title={statusIntent.operation === 'suspend' ? 'Suspendre cette organisation ?' : 'Réactiver cette organisation ?'} confirmLabel={statusIntent.operation === 'suspend' ? 'Suspendre' : 'Réactiver'} busy={busyIds.has(statusIntent.view.organization.id)} onCancel={() => setStatusIntent(null)} onConfirm={changeStatus}>
      <form className="status-operation-form" onSubmit={changeStatus}>
        <p>{statusIntent.operation === 'suspend' ? 'Les membres ne pourront plus utiliser les écrans locataires ni Google tant que l’organisation restera suspendue.' : 'Les membres actifs retrouveront l’accès. Les invitations terminales et membres désactivés ne seront pas réactivés.'}</p>
        <label htmlFor="status-reason">Raison</label>
        <select id="status-reason" value={statusIntent.reasonCode} onChange={(event) => setStatusIntent((current) => ({ ...current, reasonCode: event.target.value }))}>
          {Object.entries(REASON_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <label htmlFor="status-reference">Référence externe</label>
        <input id="status-reference" value={statusIntent.externalReference} onChange={(event) => setStatusIntent((current) => ({ ...current, externalReference: event.target.value }))} maxLength="64" pattern="[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}" placeholder="TICKET-123" />
      </form>
    </ConfirmationDialog>}
  </>
}


function OrganizationList({ busyIds, blockedResends, canManage, canManageStatus, onAbandonResend, onResend, onRevoke, onStatusChange, organizations }) {
  return <section className="administration-card resource-list-card platform-list-card" aria-labelledby="platform-list-title">
    <div className="resource-list-heading">
      <div><h2 id="platform-list-title">Organisations de la plateforme</h2><p>{organizations.items.length} organisation{organizations.items.length > 1 ? 's' : ''} chargée{organizations.items.length > 1 ? 's' : ''}, sans total global.</p></div>
      <button className="text-button" type="button" onClick={organizations.refresh} disabled={organizations.refreshing}>Actualiser</button>
    </div>
    {organizations.error && <ErrorBanner compact><span>{organizations.error}</span></ErrorBanner>}
    {!organizations.items.length ? <p className="administration-empty">Aucune organisation accessible.</p> : <ul className="platform-organization-list">
      {organizations.items.map((view) => <OrganizationRow key={view.organization.id} view={view} canManage={canManage} canManageStatus={canManageStatus} busy={busyIds.has(view.organization.id)} blocked={blockedResends.has(view.organization.id)} onAbandonResend={onAbandonResend} onResend={onResend} onRevoke={onRevoke} onStatusChange={onStatusChange} />)}
    </ul>}
    {organizations.nextCursor && <button className="secondary-button load-more-button" type="button" onClick={organizations.loadMore} disabled={organizations.loadingMore}>{organizations.loadingMore ? 'Chargement…' : 'Charger la suite'}</button>}
  </section>
}


function OrganizationRow({ blocked, busy, canManage, canManageStatus, onAbandonResend, onResend, onRevoke, onStatusChange, view }) {
  const actions = availableActions(view)
  const organizationId = view.organization.id
  return <li>
    <div className="platform-organization-identity"><strong>{view.organization.name}</strong><small>{view.organization.locale} · {view.organization.timezone}</small><small>Créée le <time dateTime={view.organization.created_at}>{formatDate(view.organization.created_at)}</time></small></div>
    <div className="platform-provisioning-state"><span className={`resource-status ${view.organization.status}`}>{ORGANIZATION_LABELS[view.organization.status] ?? view.organization.status}</span><strong>{view.first_invitation.recipient_email}</strong><span><span className={`resource-status ${view.first_invitation.state}`}>{INVITATION_LABELS[view.first_invitation.state] ?? view.first_invitation.state}</span>{' '}<span className={`delivery-status ${view.first_invitation.delivery_status}`}>{DELIVERY_LABELS[view.first_invitation.delivery_status] ?? view.first_invitation.delivery_status}</span></span><small>Expire le <time dateTime={view.first_invitation.expires_at}>{formatDate(view.first_invitation.expires_at)}</time></small></div>
    {(canManage || canManageStatus) && (actions.resend || actions.revoke || actions.suspend || actions.reactivate) && <div className="resource-actions platform-actions">
      {actions.resend && <button className="secondary-button" type="button" onClick={() => onResend(view)} disabled={busy || blocked}>{busy ? 'Traitement…' : 'Renvoyer'}</button>}
      {blocked && <button className="text-button" type="button" onClick={() => onAbandonResend(organizationId)}>Abandonner l’intention</button>}
      {actions.revoke && <button className="danger-link" type="button" onClick={() => onRevoke(view)} disabled={busy}>Révoquer</button>}
      {canManageStatus && actions.suspend && <button className="danger-link" type="button" onClick={() => onStatusChange(view, 'suspend')} disabled={busy}>Suspendre</button>}
      {canManageStatus && actions.reactivate && <button className="secondary-button" type="button" onClick={() => onStatusChange(view, 'reactivate')} disabled={busy}>Réactiver</button>}
      {actions.resend && <small>Le renvoi invalide l’ancien lien.</small>}
    </div>}
  </li>
}


function availableActions(view) {
  if (view.organization.status === 'active') return { resend: false, revoke: false, suspend: true, reactivate: false }
  if (view.organization.status === 'suspended') return { resend: false, revoke: false, suspend: false, reactivate: true }
  if (view.organization.status !== 'provisioning') return { resend: false, revoke: false, suspend: false, reactivate: false }
  const state = view.first_invitation.state
  return { resend: ['active', 'expired', 'revoked'].includes(state), revoke: ['active', 'expired'].includes(state), suspend: false, reactivate: false }
}


function actionErrorMessage(error) {
  if (error?.code === 'provisioning_outcome_unknown') return 'Le résultat est incertain. Réessayez la même action pour conserver son identifiant.'
  if (error?.code === 'idempotency_key_reused') return 'Cette clé a servi à une autre commande. Abandonnez explicitement cette intention avant un nouveau renvoi.'
  if (error?.code === 'organization_version_conflict') return 'L’organisation a changé. Actualisez la liste avant de recommencer.'
  if (error?.code === 'invalid_organization_transition') return 'Le statut courant ne permet plus cette action. Actualisez la liste.'
  if (error?.code === 'invitation_already_accepted') return 'Cette invitation a déjà été acceptée. Actualisez la liste.'
  if (error?.code === 'invitation_rate_limited') return error.retryAfter ? `Trop de renvois. Réessayez dans ${error.retryAfter} secondes.` : 'Trop de renvois. Réessayez plus tard.'
  return toUserMessage(error, 'L’opération sur l’invitation initiale a échoué.')
}


const formatDate = (value) => new Intl.DateTimeFormat('fr-CA', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const release = (reference, controller) => reference.current.delete(controller)
function track(reference) { const controller = new AbortController(); reference.current.add(controller); return controller }
function withoutKey(object, key) { const next = { ...object }; delete next[key]; return next }
function withoutSetValue(values, value) { const next = new Set(values); next.delete(value); return next }
function setBusy(reference, setter, id, busy, render = true) { const next = new Set(reference.current); if (busy) next.add(id); else next.delete(id); reference.current = next; if (render) setter(next) }
