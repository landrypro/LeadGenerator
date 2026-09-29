import { useEffect, useMemo, useState } from 'react'

import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { useMembers } from '../organizations/hooks/useMembers'
import { usageApi } from './api/usageApi'


const COPY = {
  'fr-CA': {
    title: 'Usage', intro: 'Quotas techniques et volumes d’utilisation de l’organisation.', filters: 'Portée et période',
    self: 'Mon usage', organization: 'Organisation', owner: 'Membre', scope: 'Portée', period: 'Période',
    today: 'Aujourd’hui', days7: '7 derniers jours', days30: '30 derniers jours', custom: 'Dates personnalisées',
    start: 'Du', end: 'Au', member: 'Membre', choose: 'Choisir un membre', apply: 'Afficher', loading: 'Chargement de l’usage…',
    error: 'Impossible de charger le rapport d’usage.', current: 'Quota Text Search courant', used: 'utilisées', remaining: 'restantes',
    reset: 'Remise à zéro', warning: 'Le seuil d’avertissement est atteint.', google: 'Opérations Google', platform: 'Volumes de plateforme',
    day: 'Série journalière', code: 'Opération', values: 'Mesures', exports: 'Exports CSV', imports: 'Imports CSV',
    technicalDetails: 'Détails techniques', technicalCode: 'Code de suivi', technicalUnit: 'Unité de mesure', quotaSummary: 'Réservations Text Search',
    invoice: 'Ce rapport présente des unités techniques et ne constitue pas une facture.', empty: 'Aucun usage enregistré sur cette période.',
    invalid: 'Choisir une plage valide de 93 jours au plus.',
    breakdown: 'Ventilation par membre',
    partial: 'Les données sont partielles : la période commence avant l’activation du registre qualifié.',
    partialEmpty: 'Aucune donnée qualifiée disponible sur cette partie de la période.',
    quotaUnavailable: 'Le quota temps réel est indisponible. Les valeurs affichées proviennent du registre durable.',
  },
  'en-CA': {
    title: 'Usage', intro: 'Technical quotas and usage volumes for the organization.', filters: 'Scope and period',
    self: 'My usage', organization: 'Organization', owner: 'Member', scope: 'Scope', period: 'Period',
    today: 'Today', days7: 'Last 7 days', days30: 'Last 30 days', custom: 'Custom dates', start: 'From', end: 'To',
    member: 'Member', choose: 'Choose a member', apply: 'Show', loading: 'Loading usage…', error: 'Could not load the usage report.',
    current: 'Current Text Search quota', used: 'used', remaining: 'remaining', reset: 'Reset', warning: 'The warning threshold has been reached.',
    google: 'Google operations', platform: 'Platform volumes', day: 'Daily series', code: 'Operation', values: 'Measures',
    technicalDetails: 'Technical details', technicalCode: 'Tracking code', technicalUnit: 'Unit of measure', quotaSummary: 'Text Search reservations',
    exports: 'CSV exports', imports: 'CSV imports', invoice: 'This report shows technical units and is not an invoice.',
    empty: 'No usage was recorded for this period.', invalid: 'Choose a valid range of no more than 93 days.',
    breakdown: 'By member',
    partial: 'Data is partial because the period starts before qualified collection was enabled.',
    partialEmpty: 'No qualified data is available for this part of the period.',
    quotaUnavailable: 'Real-time quota is unavailable. Displayed values come from the durable registry.',
  },
}

function count(value, locale) { return new Intl.NumberFormat(locale).format(value ?? 0) }
function dateTime(value, locale) { return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(value)) }
function date(value, locale) { return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`)) }

const OPERATION_LABELS = {
  'google.places_text_search.quota': ['Réservations de quota Text Search', 'Text Search quota reservations'],
  'google.places_text_search.request': ['Recherches d’établissements', 'Place searches'],
  'google.places_autocomplete.request': ['Suggestions de lieux', 'Place suggestions'],
  'google.places_details.request': ['Consultations de fiches établissement', 'Place detail lookups'],
  'google.maps_static.request': ['Cartes statiques', 'Static maps'],
  'platform.csv_export': ['Exports CSV', 'CSV exports'],
  'platform.csv_import': ['Imports CSV', 'CSV imports'],
}

const MEASURE_LABELS = {
  accepted: ['Acceptées', 'Accepted'], rejected: ['Refusées', 'Rejected'], attempted: ['Tentées', 'Attempted'],
  succeeded: ['Réussies', 'Succeeded'], failed: ['Échouées', 'Failed'], indeterminate: ['À confirmer', 'Pending confirmation'],
  requested: ['Demandes créées', 'Requests created'], ready: ['Fichiers prêts', 'Files ready'], expired: ['Expirés', 'Expired'],
  rows: ['Lignes exportées', 'Rows exported'], omitted: ['Lignes omises', 'Rows omitted'], bytes: ['Taille générée', 'Generated size'],
  confirmed_runs: ['Imports confirmés', 'Confirmed imports'], examined_rows: ['Lignes analysées', 'Rows reviewed'],
  created: ['Fiches créées', 'Records created'], duplicates: ['Doublons détectés', 'Duplicates detected'],
  review: ['À vérifier', 'Needs review'], quarantined: ['Mises en quarantaine', 'Quarantined'],
}

const EVENT_LABELS = {
  quota_reserved: ['Réservations de quota', 'Quota reservations'], upstream_attempted: ['Appels au fournisseur', 'Provider calls'],
  export_requested: ['Demandes d’export', 'Export requests'], export_ready: ['Exports prêts', 'Exports ready'],
  export_failed: ['Exports échoués', 'Failed exports'], export_expired: ['Exports expirés', 'Expired exports'],
  import_confirmed: ['Imports confirmés', 'Confirmed imports'], import_examined: ['Lignes analysées', 'Rows reviewed'],
  import_created: ['Fiches créées', 'Records created'], import_duplicate: ['Doublons détectés', 'Duplicates detected'],
  import_review: ['Fiches à vérifier', 'Records needing review'], import_quarantined: ['Fiches en quarantaine', 'Quarantined records'],
}

function label(labels, key, locale) {
  if (!key) return locale === 'en-CA' ? 'Event' : 'Événement'
  return labels[key]?.[locale === 'en-CA' ? 1 : 0] ?? key.replace(/[._-]+/g, ' ').replace(/^./, (letter) => letter.toUpperCase())
}
function byteCount(value, locale) { return new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format((value ?? 0) / 1024) }

function MetricList({ item, locale }) {
  return <dl className="usage-metric-list">{Object.entries(item).filter(([key]) => !['code', 'unit'].includes(key)).map(([key, value]) => <div key={key}>
    <dt>{label(MEASURE_LABELS, key, locale)}</dt><dd>{key === 'bytes' ? `${byteCount(value, locale)} Ko` : count(value, locale)}</dd>
  </div>)}</dl>
}

function TechnicalDetails({ code, unit, copy }) {
  return <details className="usage-technical-details"><summary>{copy.technicalDetails}</summary>
    <dl><div><dt>{copy.technicalCode}</dt><dd><code>{code}</code></dd></div>{unit && <div><dt>{copy.technicalUnit}</dt><dd>{unit}</dd></div>}</dl>
  </details>
}

function UsageEventList({ operations, locale }) {
  return <ul className="usage-event-list">{Object.entries(operations).map(([key, value]) => {
      const [operation, event, result] = key.split(':')
      return <li key={key}><span>{label(OPERATION_LABELS, operation, locale)} · {label(EVENT_LABELS, event, locale)}</span><strong>{label(MEASURE_LABELS, result, locale)} : {count(value, locale)}</strong></li>
    })}</ul>
}

function DailySeries({ series, locale }) {
  return <div className="usage-daily-series">{series.map((item) => <section key={item.date} className="usage-day">
    <h3><time dateTime={`${item.date}T00:00:00Z`}>{date(item.date, locale)}</time></h3>
    <UsageEventList operations={item.operations} locale={locale} />
  </section>)}</div>
}

export function UsagePage({ session }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = COPY[locale]
  const canOrganization = session.capabilities.includes('usage:read:organization')
  const members = useMembers(canOrganization)
  const [draft, setDraft] = useState({ scope: 'self', period: 'last_30_days', owner_membership_id: '', start_on: '', end_on: '' })
  const [filters, setFilters] = useState(draft)
  const [data, setData] = useState(null)
  const [current, setCurrent] = useState(null)
  const [error, setError] = useState('')
  const [filterError, setFilterError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    Promise.all([
      usageApi.report(filters, controller.signal),
      usageApi.current(filters.scope === 'organization' ? 'organization' : 'self', controller.signal),
    ]).then(([report, quota]) => { setData(report); setCurrent(quota) })
      .catch((requestError) => { if (requestError?.name !== 'AbortError') setError(toUserMessage(requestError, copy.error)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [filters, copy.error])

  const warning = current && current.limit > 0 && current.used * 100 >= current.limit * current.warning_threshold_percent
  const hasRows = useMemo(() => data?.series?.length > 0, [data])

  function apply(event) {
    event.preventDefault()
    if (draft.scope === 'owner' && !draft.owner_membership_id) { setFilterError(copy.choose); return }
    if (draft.period === 'custom') {
      const length = (Date.parse(draft.end_on) - Date.parse(draft.start_on)) / 86400000 + 1
      if (!draft.start_on || !draft.end_on || !Number.isFinite(length) || length < 1 || length > 93) { setFilterError(copy.invalid); return }
    }
    setFilterError(''); setFilters({ ...draft })
  }

  return <main className="administration-page usage-page" aria-labelledby="usage-title">
    <header className="administration-page-heading"><p className="eyebrow">Marketteo CRM</p><h1 id="usage-title">{copy.title}</h1><p>{copy.intro}</p></header>
    <form className="dashboard-filters" onSubmit={apply} aria-label={copy.filters}>
      {canOrganization && <label>{copy.scope}<select value={draft.scope} onChange={(event) => setDraft({ ...draft, scope: event.target.value })}><option value="self">{copy.self}</option><option value="organization">{copy.organization}</option><option value="owner">{copy.owner}</option></select></label>}
      {draft.scope === 'owner' && <label>{copy.member}<select value={draft.owner_membership_id} onChange={(event) => setDraft({ ...draft, owner_membership_id: event.target.value })}><option value="">{copy.choose}</option>{members.items.map((member) => <option key={member.membership_id} value={member.membership_id}>{member.user.display_name}</option>)}</select></label>}
      <label>{copy.period}<select value={draft.period} onChange={(event) => setDraft({ ...draft, period: event.target.value })}><option value="today">{copy.today}</option><option value="last_7_days">{copy.days7}</option><option value="last_30_days">{copy.days30}</option><option value="custom">{copy.custom}</option></select></label>
      {draft.period === 'custom' && <><label>{copy.start}<input type="date" value={draft.start_on} onChange={(event) => setDraft({ ...draft, start_on: event.target.value })} /></label><label>{copy.end}<input type="date" value={draft.end_on} onChange={(event) => setDraft({ ...draft, end_on: event.target.value })} /></label></>}
      <button className="primary-button" type="submit">{copy.apply}</button>{filterError && <p role="alert">{filterError}</p>}
    </form>
    {loading && <p role="status" className="administration-loading">{copy.loading}</p>}
    {error && <ErrorBanner>{error}</ErrorBanner>}
    {data && current && <>
      <p className="dashboard-asof">{data.period.start_on} – {data.period.end_on} (UTC)</p>
      {data.completeness?.status === 'partial' && <p role="status" className="usage-warning">{copy.partial}</p>}
      <section className="dashboard-panel"><h2>{copy.current}</h2><p><strong>{copy.quotaSummary} : {count(current.used, locale)} {copy.used} sur {count(current.limit, locale)}</strong> · {count(current.remaining, locale)} {copy.remaining}</p><p>{copy.reset}: {dateTime(current.reset_at, locale)} UTC.</p><TechnicalDetails code={`${current.policy_code} · ${current.source}`} unit={current.unit} copy={copy} />{current.enforcement_status !== 'available' && <p role="status" className="usage-warning">{copy.quotaUnavailable}</p>}{warning && <p role="status" className="usage-warning">{copy.warning}</p>}</section>
      <section className="dashboard-panel"><h2>{copy.google}</h2><div className="usage-operation-list">{data.google.totals.map((item) => <article key={item.code} className="usage-operation"><h3>{label(OPERATION_LABELS, item.code, locale)}</h3><MetricList item={item} locale={locale} /><TechnicalDetails code={item.code} unit={item.unit} copy={copy} /></article>)}</div></section>
      <section className="dashboard-panel"><h2>{copy.platform}</h2><dl className="usage-volumes"><div><dt>{copy.exports}</dt><dd><MetricList item={data.platform.csv_export} locale={locale} /></dd></div><div><dt>{copy.imports}</dt><dd><MetricList item={data.platform.csv_import} locale={locale} /></dd></div></dl></section>
      <section className="dashboard-panel"><h2>{copy.day}</h2>{hasRows ? <DailySeries series={data.series} locale={locale} /> : <p>{data.completeness?.status === 'complete' ? copy.empty : copy.partialEmpty}</p>}</section>
      {data.owner_breakdown?.length > 0 && <section className="dashboard-panel"><h2>{copy.breakdown}</h2>{data.owner_breakdown.map((item) => <details key={item.owner_membership_id}><summary>{members.items.find((member) => member.membership_id === item.owner_membership_id)?.user.display_name ?? item.owner_membership_id}</summary><UsageEventList operations={item.operations} locale={locale} /></details>)}</section>}
      <p className="dashboard-attribution">{copy.invoice}</p>
    </>}
  </main>
}
