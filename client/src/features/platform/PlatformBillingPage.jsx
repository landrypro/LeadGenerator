import { useEffect, useRef, useState } from 'react'

import { toUserMessage } from '../../shared/api/errors'
import { createRequestId } from '../../shared/ids/requestId'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { platformApi } from './api/platformApi'


const STATE_LABELS = {
  pending: 'Contrat en attente', pending_checkout: 'Checkout en attente', pending_approval: 'En attente d’approbation',
  active: 'Actif', past_due: 'Paiement à régulariser', grace_period: 'Délai de régularisation',
  suspended: 'Suspendu', canceling: 'Annulation programmée', canceled: 'Terminé',
  expired: 'Expirée', revoked: 'Révoquée', none: 'Aucun état',
}
const SOURCE_LABELS = {
  stripe: 'Stripe', simulated: 'Simulé', catalog_only: 'Contrat catalogue',
  manual_grant: 'Attribution sandbox', none: 'Aucune source',
}
const REVIEW_LABELS = { needs_review: 'À vérifier', not_checked: 'Non rapproché' }
const REASON_LABELS = {
  sandbox_validation: 'Validation sandbox', sandbox_support: 'Support sandbox', sandbox_demonstration: 'Démonstration sandbox',
}


function date(value, locale) {
  return value ? new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
}

function price(value, currency, locale) {
  return new Intl.NumberFormat(locale, {
    style: 'currency', currency, minimumFractionDigits: currency === 'XAF' ? 0 : 2, maximumFractionDigits: currency === 'XAF' ? 0 : 2,
  }).format(value / (currency === 'XAF' ? 1 : 100))
}

function organizationState(item) {
  return item.subscription_state || item.contract_state || item.manual_grant_state || 'none'
}

export function PlatformBillingPage({ session }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const [filters, setFilters] = useState({ state: '', source: '' })
  const [items, setItems] = useState([])
  const [nextCursor, setNextCursor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailError, setDetailError] = useState('')
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [grantOptions, setGrantOptions] = useState([])
  const [loadingGrantOptions, setLoadingGrantOptions] = useState(false)
  const [grantOptionsError, setGrantOptionsError] = useState('')
  const [manualGrantsAvailable, setManualGrantsAvailable] = useState(true)
  const [grantForm, setGrantForm] = useState({ plan_version_id: '', reason_code: 'sandbox_validation', duration_days: '31' })
  const [grantError, setGrantError] = useState('')
  const [grantSuccess, setGrantSuccess] = useState('')
  const [grantSubmitting, setGrantSubmitting] = useState(false)
  const listController = useRef(null)
  const detailController = useRef(null)
  const optionsController = useRef(null)
  const grantCommand = useRef(null)

  async function load({ more = false, cursor = '' } = {}) {
    listController.current?.abort()
    const controller = new AbortController()
    listController.current = controller
    more ? setLoadingMore(true) : setLoading(true)
    setError('')
    try {
      const page = await platformApi.listBillingOrganizations({ ...filters, cursor }, controller.signal)
      if (controller.signal.aborted) return
      setItems(current => more ? [...current, ...page.items.filter(item => !current.some(known => known.id === item.id))] : page.items)
      setNextCursor(page.next_cursor)
    } catch (requestError) {
      if (!controller.signal.aborted) setError(toUserMessage(requestError, 'Impossible de charger la consultation Billing.'))
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
        setLoadingMore(false)
      }
    }
  }

  useEffect(() => {
    setSelected(null)
    setDetail(null)
    void load()
    return () => listController.current?.abort()
  // The filter object is deliberately replaced, not mutated.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters])

  async function loadGrantOptions() {
    optionsController.current?.abort()
    const controller = new AbortController()
    optionsController.current = controller
    setLoadingGrantOptions(true)
    setGrantOptionsError('')
    setManualGrantsAvailable(true)
    try {
      const options = await platformApi.listManualBillingGrantOptions(controller.signal)
      if (!controller.signal.aborted) setGrantOptions(options)
    } catch (requestError) {
      if (!controller.signal.aborted) {
        if (requestError?.code === 'billing_provider_disabled') {
          setManualGrantsAvailable(false)
          setGrantOptions([])
        } else {
          setGrantOptionsError(toUserMessage(requestError, 'Impossible de charger les forfaits sandbox.'))
        }
      }
    } finally {
      if (!controller.signal.aborted) setLoadingGrantOptions(false)
    }
  }

  async function selectOrganization(organization) {
    detailController.current?.abort()
    const controller = new AbortController()
    detailController.current = controller
    setSelected(organization.id)
    setDetail(null)
    setDetailError('')
    setGrantError('')
    setGrantSuccess('')
    setGrantForm({ plan_version_id: '', reason_code: 'sandbox_validation', duration_days: '31' })
    grantCommand.current = null
    setLoadingDetail(true)
    void loadGrantOptions()
    try {
      const response = await platformApi.getBillingOrganization(organization.id, controller.signal)
      if (!controller.signal.aborted) setDetail(response)
    } catch (requestError) {
      if (!controller.signal.aborted) setDetailError(toUserMessage(requestError, 'Impossible de charger le détail Billing.'))
    } finally {
      if (!controller.signal.aborted) setLoadingDetail(false)
    }
  }

  async function refreshSelected() {
    if (!selected) return
    const response = await platformApi.getBillingOrganization(selected)
    setDetail(response)
    await load()
  }

  function idempotencyKey(signature) {
    if (grantCommand.current?.signature === signature) return grantCommand.current.key
    const key = createRequestId()
    grantCommand.current = { signature, key }
    return key
  }

  async function proposeGrant(event) {
    event.preventDefault()
    if (!selected || grantSubmitting || !grantForm.plan_version_id) return
    const payload = { ...grantForm, organization_id: selected, duration_days: Number(grantForm.duration_days) }
    const signature = `propose:${JSON.stringify(payload)}`
    setGrantSubmitting(true)
    setGrantError('')
    setGrantSuccess('')
    try {
      await platformApi.proposeManualBillingGrant(payload, idempotencyKey(signature))
      grantCommand.current = null
      setGrantSuccess('Attribution sandbox proposée. Un autre administrateur plateforme doit l’approuver avant tout accès.')
      await refreshSelected()
    } catch (requestError) {
      setGrantError(toUserMessage(requestError, 'Impossible de proposer l’attribution sandbox.'))
    } finally {
      setGrantSubmitting(false)
    }
  }

  async function mutateGrant(action) {
    const grant = detail?.manual_grant
    if (!grant || grantSubmitting) return
    const signature = `${action}:${grant.id}:${grant.version}`
    setGrantSubmitting(true)
    setGrantError('')
    setGrantSuccess('')
    try {
      if (action === 'approve') await platformApi.approveManualBillingGrant(grant.id, grant.version, idempotencyKey(signature))
      else await platformApi.revokeManualBillingGrant(grant.id, grant.version, idempotencyKey(signature))
      grantCommand.current = null
      setGrantSuccess(action === 'approve'
        ? 'Attribution sandbox approuvée. Aucun paiement ni abonnement Stripe n’a été créé.'
        : 'Attribution sandbox révoquée.')
      await refreshSelected()
    } catch (requestError) {
      setGrantError(toUserMessage(requestError, 'Impossible de modifier l’attribution sandbox.'))
    } finally {
      setGrantSubmitting(false)
    }
  }

  const manualGrant = detail?.manual_grant
  const canProposeGrant = !manualGrant || ['expired', 'revoked'].includes(manualGrant.state)
  const canApproveGrant = manualGrant?.state === 'pending_approval'
  const canRevokeGrant = manualGrant && ['pending_approval', 'active'].includes(manualGrant.state)

  return <main className="administration-page platform-page" aria-labelledby="platform-billing-title">
    <header className="administration-page-heading members-page-heading">
      <div><p className="eyebrow">Administration de la plateforme</p><h1 id="platform-billing-title">Consultation Billing</h1>
        <p>Consultez les projections de contrat et d’abonnement, puis gérez seulement les exceptions sandbox explicitement approuvées.</p></div>
    </header>

    <section className="administration-card" aria-label="Filtres de la consultation Billing">
      <div className="platform-form-grid">
        <label className="platform-form-field" htmlFor="platform-billing-state">État
          <select id="platform-billing-state" value={filters.state} onChange={event => setFilters(current => ({ ...current, state: event.target.value }))}>
            <option value="">Tous les états</option>{Object.entries(STATE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="platform-form-field" htmlFor="platform-billing-source">Origine
          <select id="platform-billing-source" value={filters.source} onChange={event => setFilters(current => ({ ...current, source: event.target.value }))}>
            <option value="">Toutes les origines</option>{Object.entries(SOURCE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      </div>
      <button type="button" className="secondary-button" onClick={() => void load()} disabled={loading}>Actualiser</button>
    </section>

    <section className="administration-card" aria-labelledby="platform-billing-list-title">
      <h2 id="platform-billing-list-title">Organisations</h2>
      {loading && <p role="status">Chargement des projections Billing…</p>}
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {!loading && !error && items.length === 0 && <p role="status">Aucune organisation ne correspond à ces filtres.</p>}
      {!loading && items.length > 0 && <div className="platform-organization-list">
        {items.map(item => <button type="button" key={item.id} className="platform-organization-row" onClick={() => void selectOrganization(item)} aria-pressed={selected === item.id}>
          <span><strong>{item.name}</strong><small>{item.plan_code ? `${item.plan_code} · v${item.version_number ?? '—'} · ${item.currency ?? '—'}` : 'Aucun forfait'}</small></span>
          <span><small>{STATE_LABELS[organizationState(item)]}</small><small>{SOURCE_LABELS[item.source]} · {REVIEW_LABELS[item.reconciliation_status]}</small></span>
        </button>)}
      </div>}
      {nextCursor && <button type="button" className="secondary-button" onClick={() => void load({ more: true, cursor: nextCursor })} disabled={loadingMore}>
        {loadingMore ? 'Chargement…' : 'Afficher plus'}
      </button>}
    </section>

    {selected && <section className="administration-card" aria-labelledby="platform-billing-detail-title">
      <h2 id="platform-billing-detail-title">Détail de la projection</h2>
      {loadingDetail && <p role="status">Chargement du détail…</p>}
      {detailError && <ErrorBanner>{detailError}</ErrorBanner>}
      {detail && <>
        <dl className="account-details-grid">
          <div><dt>Organisation</dt><dd>{detail.organization.name}</dd></div>
          <div><dt>Forfait</dt><dd>{detail.organization.plan_code ? `${detail.organization.plan_code} · v${detail.organization.version_number ?? '—'} · ${detail.organization.currency ?? '—'}` : 'Aucun forfait'}</dd></div>
          <div><dt>État</dt><dd>{STATE_LABELS[organizationState(detail.organization)]}</dd></div>
          <div><dt>Origine</dt><dd>{SOURCE_LABELS[detail.organization.source]}</dd></div>
          <div><dt>Échéance</dt><dd>{date(detail.organization.current_period_end, locale)}</dd></div>
          <div><dt>Rapprochement</dt><dd>{REVIEW_LABELS[detail.organization.reconciliation_status]}</dd></div>
        </dl>

        {manualGrantsAvailable && <section className="platform-billing-grant" aria-labelledby="platform-manual-grant-title">
          <h3 id="platform-manual-grant-title">Attribution administrative sandbox</h3>
          <p className="form-help">Cette exception n’est ni une facture, ni un paiement, ni un abonnement Stripe. Elle est limitée à 31 jours et exige un approbateur plateforme distinct.</p>
          {manualGrant && <dl className="account-details-grid">
            <div><dt>État</dt><dd>{STATE_LABELS[manualGrant.state]}</dd></div>
            <div><dt>Forfait temporaire</dt><dd>{manualGrant.plan_code} · v{manualGrant.version_number} · {manualGrant.currency}</dd></div>
            <div><dt>Motif</dt><dd>{REASON_LABELS[manualGrant.reason_code]}</dd></div>
            <div><dt>Durée</dt><dd>{manualGrant.duration_days} jour(s)</dd></div>
            <div><dt>Début</dt><dd>{date(manualGrant.starts_at, locale)}</dd></div>
            <div><dt>Fin</dt><dd>{date(manualGrant.ends_at, locale)}</dd></div>
          </dl>}
          {grantOptionsError && <ErrorBanner>{grantOptionsError}</ErrorBanner>}
          {grantError && <ErrorBanner>{grantError}</ErrorBanner>}
          {grantSuccess && <p className="account-note" role="status">{grantSuccess}</p>}
          {canProposeGrant && <form className="platform-form-grid" onSubmit={proposeGrant}>
            <label className="platform-form-field" htmlFor="manual-grant-plan">Forfait sandbox
              <select id="manual-grant-plan" required disabled={loadingGrantOptions || grantSubmitting} value={grantForm.plan_version_id}
                onChange={event => setGrantForm(current => ({ ...current, plan_version_id: event.target.value }))}>
                <option value="">Choisir un forfait</option>
                {grantOptions.map(option => <option key={option.plan_version_id} value={option.plan_version_id}>
                  {option.code} · v{option.version_number} · {price(option.amount_minor, option.currency, locale)} {option.currency}
                </option>)}
              </select>
            </label>
            <label className="platform-form-field" htmlFor="manual-grant-reason">Motif fermé
              <select id="manual-grant-reason" disabled={grantSubmitting} value={grantForm.reason_code}
                onChange={event => setGrantForm(current => ({ ...current, reason_code: event.target.value }))}>
                {Object.entries(REASON_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="platform-form-field" htmlFor="manual-grant-days">Durée (jours)
              <input id="manual-grant-days" type="number" min="1" max="31" required disabled={grantSubmitting} value={grantForm.duration_days}
                onChange={event => setGrantForm(current => ({ ...current, duration_days: event.target.value }))} />
            </label>
            <div><button className="primary-button" type="submit" disabled={grantSubmitting || loadingGrantOptions || !grantForm.plan_version_id}>
              {grantSubmitting ? 'Proposition…' : 'Proposer l’attribution sandbox'}
            </button></div>
          </form>}
          {loadingGrantOptions && canProposeGrant && <p role="status">Chargement des forfaits sandbox…</p>}
          {canApproveGrant && <p className="account-note">Cette proposition doit être approuvée par un autre administrateur plateforme.</p>}
          {canApproveGrant && <button type="button" className="primary-button" onClick={() => void mutateGrant('approve')} disabled={grantSubmitting}>
            {grantSubmitting ? 'Approbation…' : 'Approuver l’attribution'}
          </button>}
          {canRevokeGrant && <button type="button" className="secondary-button" onClick={() => void mutateGrant('revoke')} disabled={grantSubmitting}>
            {grantSubmitting ? 'Révocation…' : 'Révoquer l’attribution'}
          </button>}
        </section>}

        <h3>Événements applicatifs</h3>
        {detail.events.length ? <ul>{detail.events.map((event, index) => <li key={`${event.event_type}-${event.occurred_at}-${index}`}>{event.event_type} — {date(event.occurred_at, locale)}</li>)}</ul> : <p>Aucun événement à afficher.</p>}
        <h3>Interventions et commandes</h3>
        {detail.interventions.length ? <ul>{detail.interventions.map((item, index) => <li key={`${item.kind}-${item.created_at}-${index}`}>{item.kind} · {item.status} — {date(item.updated_at, locale)}</li>)}</ul> : <p>Aucune intervention à afficher.</p>}
      </>}
    </section>}
  </main>
}
