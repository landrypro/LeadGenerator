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
function measures(item, locale) {
  return Object.entries(item).filter(([key]) => !['code', 'unit'].includes(key)).map(([key, value]) => `${key}: ${count(value, locale)}`).join(' · ')
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
      <section className="dashboard-panel"><h2>{copy.current}</h2><p><strong>{count(current.used, locale)} / {count(current.limit, locale)}</strong> {copy.used} · {count(current.remaining, locale)} {copy.remaining}</p><p>{copy.reset}: {dateTime(current.reset_at, locale)} UTC · {current.unit} · {current.policy_code} · {current.source}</p>{current.enforcement_status !== 'available' && <p role="status" className="usage-warning">{copy.quotaUnavailable}</p>}{warning && <p role="status" className="usage-warning">{copy.warning}</p>}</section>
      <section className="dashboard-panel"><h2>{copy.google}</h2><div className="dashboard-table-scroll"><table><thead><tr><th scope="col">{copy.code}</th><th scope="col">{copy.values}</th></tr></thead><tbody>{data.google.totals.map((item) => <tr key={item.code}><th scope="row">{item.code}<small>{item.unit}</small></th><td>{measures(item, locale)}</td></tr>)}</tbody></table></div></section>
      <section className="dashboard-panel"><h2>{copy.platform}</h2><dl className="usage-volumes"><div><dt>{copy.exports}</dt><dd>{measures(data.platform.csv_export, locale)}</dd></div><div><dt>{copy.imports}</dt><dd>{measures(data.platform.csv_import, locale)}</dd></div></dl></section>
      <section className="dashboard-panel"><h2>{copy.day}</h2>{hasRows ? <div className="dashboard-table-scroll"><table><thead><tr><th scope="col">UTC</th><th scope="col">{copy.values}</th></tr></thead><tbody>{data.series.map((item) => <tr key={item.date}><th scope="row">{item.date}</th><td>{Object.entries(item.operations).map(([key, value]) => `${key}: ${count(value, locale)}`).join(' · ')}</td></tr>)}</tbody></table></div> : <p>{data.completeness?.status === 'complete' ? copy.empty : copy.partialEmpty}</p>}</section>
      {data.owner_breakdown?.length > 0 && <section className="dashboard-panel"><h2>{copy.breakdown}</h2>{data.owner_breakdown.map((item) => <details key={item.owner_membership_id}><summary>{members.items.find((member) => member.membership_id === item.owner_membership_id)?.user.display_name ?? item.owner_membership_id}</summary><p>{Object.entries(item.operations).map(([key, value]) => `${key}: ${count(value, locale)}`).join(' · ')}</p></details>)}</section>}
      <p className="dashboard-attribution">{copy.invoice}</p>
    </>}
  </main>
}
