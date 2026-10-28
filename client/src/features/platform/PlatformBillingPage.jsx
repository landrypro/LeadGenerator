import { useEffect, useRef, useState } from 'react'

import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { platformApi } from './api/platformApi'


const STATE_LABELS = {
  pending_checkout: 'Checkout en attente', active: 'Actif', past_due: 'Paiement à régulariser',
  grace_period: 'Délai de régularisation', suspended: 'Suspendu', canceling: 'Annulation programmée',
  canceled: 'Terminé', none: 'Aucun état',
}
const SOURCE_LABELS = { stripe: 'Stripe', simulated: 'Simulé', catalog_only: 'Contrat catalogue', none: 'Aucune source' }
const REVIEW_LABELS = { needs_review: 'À vérifier', not_checked: 'Non rapproché' }

function date(value, locale) {
  return value ? new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
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
  const listController = useRef(null)
  const detailController = useRef(null)

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

  async function selectOrganization(organization) {
    detailController.current?.abort()
    const controller = new AbortController()
    detailController.current = controller
    setSelected(organization.id)
    setDetail(null)
    setDetailError('')
    setLoadingDetail(true)
    try {
      const response = await platformApi.getBillingOrganization(organization.id, controller.signal)
      if (!controller.signal.aborted) setDetail(response)
    } catch (requestError) {
      if (!controller.signal.aborted) setDetailError(toUserMessage(requestError, 'Impossible de charger le détail Billing.'))
    } finally {
      if (!controller.signal.aborted) setLoadingDetail(false)
    }
  }

  return <main className="administration-page platform-page" aria-labelledby="platform-billing-title">
    <header className="administration-page-heading members-page-heading">
      <div><p className="eyebrow">Administration de la plateforme</p><h1 id="platform-billing-title">Consultation Billing</h1>
        <p>Consultez les projections de contrat et d’abonnement. Cette vue ne modifie aucun forfait ni paiement.</p></div>
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
          <span><small>{STATE_LABELS[item.subscription_state || item.contract_state || 'none']}</small><small>{SOURCE_LABELS[item.source]} · {REVIEW_LABELS[item.reconciliation_status]}</small></span>
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
          <div><dt>État</dt><dd>{STATE_LABELS[detail.organization.subscription_state || detail.organization.contract_state || 'none']}</dd></div>
          <div><dt>Échéance</dt><dd>{date(detail.organization.current_period_end, locale)}</dd></div>
          <div><dt>Annulation</dt><dd>{detail.organization.cancel_at_period_end ? 'Programmée' : 'Non programmée'}</dd></div>
          <div><dt>Rapprochement</dt><dd>{REVIEW_LABELS[detail.organization.reconciliation_status]}</dd></div>
        </dl>
        <h3>Événements applicatifs</h3>
        {detail.events.length ? <ul>{detail.events.map((event, index) => <li key={`${event.event_type}-${event.occurred_at}-${index}`}>{event.event_type} — {date(event.occurred_at, locale)}</li>)}</ul> : <p>Aucun événement à afficher.</p>}
        <h3>Interventions et commandes</h3>
        {detail.interventions.length ? <ul>{detail.interventions.map((item, index) => <li key={`${item.kind}-${item.created_at}-${index}`}>{item.kind} · {item.status} — {date(item.updated_at, locale)}</li>)}</ul> : <p>Aucune intervention à afficher.</p>}
      </>}
    </section>}
  </main>
}
