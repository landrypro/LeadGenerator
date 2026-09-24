import { useEffect, useRef, useState } from 'react'

import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { useMembers } from '../organizations/hooks/useMembers'
import { dashboardApi } from './api/dashboardApi'


const LABELS = {
  'fr-CA': {
    title: 'Tableau de bord', intro: 'Vue commerciale de l’organisation active.',
    filters: 'Périmètre et période', scope: 'Périmètre', self: 'Mes données', organization: 'Organisation', owner: 'Commercial',
    ownerLabel: 'Responsable', chooseOwner: 'Choisir un membre', moreMembers: 'Charger d’autres membres',
    disabled: 'désactivé',
    day: 'Aujourd’hui', week: 'Cette semaine', month: 'Ce mois', custom: 'Dates personnalisées',
    period: 'Période', start: 'Du', end: 'Au', apply: 'Afficher', refresh: 'Actualiser',
    loading: 'Chargement des indicateurs…', error: 'Impossible de charger le tableau de bord.', retry: 'Réessayer',
    snapshot: 'Photographie actuelle', flow: 'Flux de la période', asOf: 'Données au', observed: 'Observé jusqu’au',
    noPeriod: 'Aucune activité ni progression dans cette période.', insufficient: 'Données insuffisantes',
    prospects: 'Prospects par étape', stage: 'Étape', count: 'Nombre', tasks: 'Tâches à traiter', dueToday: 'Dues aujourd’hui', overdue: 'En retard',
    activities: 'Activités par type', activity: 'Type', passage: 'Passage direct dans la période', from: 'De', to: 'Vers',
    cohort: 'Cohorte', advanced: 'Avancés', rate: 'Taux', losses: 'Pertes directes', lost: 'Perdus',
    opportunities: 'Opportunités', open: 'Ouvertes', won: 'Gagnées', lostOpp: 'Perdues',
    pipeline: 'Pipeline par devise', currency: 'Devise', amount: 'Montant ouvert', weighted: 'Valeur pondérée',
    breakdown: 'Ventilation par responsable', unassigned: 'Non assigné',
    attribution: 'Les passages historiques sont attribués au responsable actuel du prospect. Une réaffectation peut modifier cette ventilation.',
    google: 'Usage Google', unavailable: 'Compteur indisponible : la source d’usage n’est pas encore qualifiée.',
    noData: 'Aucune donnée', invalidDates: 'Choisir une plage valide de 93 jours au plus.',
    noPermission: 'Vous n’avez pas accès à ce périmètre.', ownerNotFound: 'Responsable introuvable dans cette organisation.',
  },
  'en-CA': {
    title: 'Dashboard', intro: 'Sales overview for the active organization.',
    filters: 'Scope and period', scope: 'Scope', self: 'My data', organization: 'Organization', owner: 'Sales member',
    ownerLabel: 'Owner', chooseOwner: 'Choose a member', moreMembers: 'Load more members',
    disabled: 'disabled',
    day: 'Today', week: 'This week', month: 'This month', custom: 'Custom dates',
    period: 'Period', start: 'From', end: 'To', apply: 'Show', refresh: 'Refresh',
    loading: 'Loading metrics…', error: 'Could not load the dashboard.', retry: 'Retry',
    snapshot: 'Current snapshot', flow: 'Period activity', asOf: 'Data as of', observed: 'Observed until',
    noPeriod: 'No activity or progress in this period.', insufficient: 'Insufficient data',
    prospects: 'Prospects by stage', stage: 'Stage', count: 'Count', tasks: 'Tasks to handle', dueToday: 'Due today', overdue: 'Overdue',
    activities: 'Activities by type', activity: 'Type', passage: 'Direct stage passage in the period', from: 'From', to: 'To',
    cohort: 'Cohort', advanced: 'Advanced', rate: 'Rate', losses: 'Direct losses', lost: 'Lost',
    opportunities: 'Opportunities', open: 'Open', won: 'Won', lostOpp: 'Lost',
    pipeline: 'Pipeline by currency', currency: 'Currency', amount: 'Open amount', weighted: 'Weighted value',
    breakdown: 'By owner', unassigned: 'Unassigned',
    attribution: 'Historical stage passages use the prospect’s current owner. Reassignment can change this breakdown.',
    google: 'Google usage', unavailable: 'Metric unavailable: the usage source has not been qualified.',
    noData: 'No data', invalidDates: 'Choose a valid range of at most 93 days.',
    noPermission: 'You cannot access this scope.', ownerNotFound: 'Owner not found in this organization.',
  },
}

const STAGES = {
  new: ['Nouveau', 'New'], qualifying: ['En qualification', 'Qualifying'], qualified: ['Qualifié', 'Qualified'],
  contacted: ['Contacté', 'Contacted'], opportunity: ['Opportunité', 'Opportunity'], proposal_sent: ['Proposition envoyée', 'Proposal sent'],
  negotiation: ['Négociation', 'Negotiation'], won: ['Gagné', 'Won'], lost: ['Perdu', 'Lost'],
}
const ACTIVITIES = { call: ['Appel', 'Call'], meeting: ['Rendez-vous', 'Meeting'], email: ['Courriel', 'Email'], note: ['Note', 'Note'] }

function translated(values, code, locale) { return values[code]?.[locale === 'en-CA' ? 1 : 0] ?? code }
function number(value, locale) { return new Intl.NumberFormat(locale).format(value ?? 0) }
function money(value, currency, locale) {
  return new Intl.NumberFormat(locale, { style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(value)
}
function dateTime(value, locale, timezone) {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', timeZone: timezone }).format(new Date(value))
}

function DataTable({ title, headers, rows, empty }) {
  return <section className="dashboard-panel" aria-label={title}>
    <h3>{title}</h3>
    {rows.length ? <div className="dashboard-table-scroll"><table><caption className="sr-only">{title}</caption>
      <thead><tr>{headers.map((header) => <th scope="col" key={header}>{header}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, column) => column === 0
        ? <th scope="row" key={column}>{cell}</th> : <td key={column}>{cell}</td>)}</tr>)}</tbody>
    </table></div> : <p>{empty}</p>}
  </section>
}

function SummarySections({ data, locale, labels, timezone, compact = false }) {
  const stage = (code) => translated(STAGES, code, locale)
  const activity = (code) => translated(ACTIVITIES, code, locale)
  return <div className={compact ? 'dashboard-sections dashboard-compact' : 'dashboard-sections'}>
    <div className="dashboard-section-heading"><h2>{labels.snapshot}</h2></div>
    <div className="dashboard-grid">
      <DataTable title={labels.prospects} headers={[labels.stage, labels.count]} empty={labels.noData}
        rows={data.prospects_by_stage.filter((item) => item.count > 0).map((item) => [stage(item.stage_code), number(item.count, locale)])} />
      <DataTable title={labels.tasks} headers={[labels.stage, labels.count]} empty={labels.noData}
        rows={[[labels.dueToday, number(data.tasks.due_today, locale)], [labels.overdue, number(data.tasks.overdue, locale)]]} />
      <DataTable title={labels.opportunities} headers={[labels.stage, labels.count]} empty={labels.noData}
        rows={[[labels.open, number(data.opportunities.open, locale)], [labels.won, number(data.opportunities.won, locale)], [labels.lostOpp, number(data.opportunities.lost, locale)]]} />
      <DataTable title={labels.pipeline} headers={[labels.currency, labels.amount, labels.weighted]} empty={labels.noData}
        rows={data.pipeline_by_currency.map((item) => [item.currency_code, money(item.amount, item.currency_code, locale), money(item.weighted_amount, item.currency_code, locale)])} />
    </div>
    <div className="dashboard-section-heading"><h2>{labels.flow}</h2></div>
    <div className="dashboard-grid">
      <DataTable title={labels.activities} headers={[labels.activity, labels.count]} empty={labels.noData}
        rows={data.activities_by_type.filter((item) => item.count > 0).map((item) => [activity(item.type), number(item.count, locale)])} />
      <DataTable title={labels.passage} headers={[labels.from, labels.to, labels.cohort, labels.advanced, labels.rate]} empty={labels.noData}
        rows={data.stage_passage.map((item) => [stage(item.from_stage), stage(item.to_stage), number(item.cohort, locale), number(item.advanced, locale), item.rate_percent === null ? labels.insufficient : `${number(Number(item.rate_percent), locale)} %`])} />
      <DataTable title={labels.losses} headers={[labels.from, labels.cohort, labels.lost]} empty={labels.noData}
        rows={data.stage_losses.map((item) => [stage(item.from_stage), number(item.cohort, locale), number(item.lost, locale)])} />
    </div>
    {!compact && <p className="dashboard-observation">{labels.observed} {dateTime(data.stage_passage[0]?.observed_until ?? data.as_of, locale, timezone)}</p>}
  </div>
}

export function DashboardPage({ session }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const labels = LABELS[locale]
  const canOrganization = session.capabilities.includes('dashboard:read:organization')
  const members = useMembers(canOrganization)
  const [draft, setDraft] = useState({ scope: 'self', period: 'month', owner_membership_id: '', start_on: '', end_on: '' })
  const [filters, setFilters] = useState(draft)
  const [refresh, setRefresh] = useState(0)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filterError, setFilterError] = useState('')
  const controllerRef = useRef(null)
  const timezone = summary?.period?.timezone ?? session.active_organization?.timezone ?? 'America/Toronto'

  useEffect(() => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setSummary(null)
    setLoading(true)
    setError('')
    dashboardApi.summary(filters, controller.signal).then((result) => {
      if (!controller.signal.aborted) setSummary(result)
    }).catch((requestError) => {
      if (requestError?.name !== 'AbortError' && !controller.signal.aborted) {
        const message = requestError?.status === 403 ? labels.noPermission
          : requestError?.status === 404 ? labels.ownerNotFound
            : requestError?.status === 422 ? labels.invalidDates
              : toUserMessage(requestError, labels.error)
        setError(message)
      }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [filters, refresh, labels.error, labels.invalidDates, labels.noPermission, labels.ownerNotFound])

  function apply(event) {
    event.preventDefault()
    if (draft.scope === 'owner' && !draft.owner_membership_id) { setFilterError(labels.chooseOwner); return }
    if (draft.period === 'custom') {
      const length = (Date.parse(draft.end_on) - Date.parse(draft.start_on)) / 86400000 + 1
      if (!draft.start_on || !draft.end_on || !Number.isFinite(length) || length < 1 || length > 93) {
        setFilterError(labels.invalidDates); return
      }
    }
    setFilterError('')
    setFilters({ ...draft })
    setRefresh((value) => value + 1)
  }

  const periodEmpty = summary && summary.activities_by_type.every((item) => item.count === 0)
    && summary.stage_passage.every((item) => item.cohort === 0)

  return <main className="administration-page dashboard-page" aria-labelledby="dashboard-title">
    <header className="administration-page-heading"><p className="eyebrow">Marketteo CRM</p><h1 id="dashboard-title">{labels.title}</h1><p>{labels.intro}</p></header>
    <form className="dashboard-filters" onSubmit={apply} aria-label={labels.filters}>
      {canOrganization && <label>{labels.scope}<select value={draft.scope} onChange={(event) => setDraft({ ...draft, scope: event.target.value })}>
        <option value="self">{labels.self}</option><option value="organization">{labels.organization}</option><option value="owner">{labels.owner}</option>
      </select></label>}
      {canOrganization && draft.scope === 'owner' && <label>{labels.ownerLabel}<select value={draft.owner_membership_id} onChange={(event) => setDraft({ ...draft, owner_membership_id: event.target.value })}>
        <option value="">{labels.chooseOwner}</option>{members.items.map((member) => <option key={member.membership_id} value={member.membership_id}>{member.user.display_name} ({member.user.email}){member.status === 'disabled' ? ` — ${labels.disabled}` : ''}</option>)}
      </select></label>}
      {canOrganization && draft.scope === 'owner' && members.nextCursor && <button className="link-button" type="button" onClick={members.loadMore}>{labels.moreMembers}</button>}
      {canOrganization && draft.scope === 'owner' && members.error && <p role="alert">{members.error}</p>}
      <label>{labels.period}<select value={draft.period} onChange={(event) => setDraft({ ...draft, period: event.target.value })}>
        <option value="day">{labels.day}</option><option value="week">{labels.week}</option><option value="month">{labels.month}</option><option value="custom">{labels.custom}</option>
      </select></label>
      {draft.period === 'custom' && <><label>{labels.start}<input type="date" value={draft.start_on} onChange={(event) => setDraft({ ...draft, start_on: event.target.value })} /></label>
        <label>{labels.end}<input type="date" value={draft.end_on} onChange={(event) => setDraft({ ...draft, end_on: event.target.value })} /></label></>}
      <button className="primary-button" type="submit">{labels.apply}</button>
      <button className="secondary-button" type="button" onClick={() => setRefresh((value) => value + 1)}>{labels.refresh}</button>
      {filterError && <p role="alert" className="dashboard-filter-error">{filterError}</p>}
    </form>
    {loading && <p role="status" className="administration-loading">{labels.loading}</p>}
    {error && <ErrorBanner><span>{error}</span><button type="button" className="link-button" onClick={() => setRefresh((value) => value + 1)}>{labels.retry}</button></ErrorBanner>}
    {summary && <>
      <p className="dashboard-asof">{labels.asOf} {dateTime(summary.as_of, locale, timezone)} · {summary.period.start_on} – {summary.period.end_on} ({timezone})</p>
      {periodEmpty && <p className="dashboard-empty" role="status">{labels.noPeriod}</p>}
      <SummarySections data={summary} locale={locale} labels={labels} timezone={timezone} />
      <p className="dashboard-attribution">{labels.attribution}</p>
      <section className="dashboard-panel"><h2>{labels.google}</h2><p>{labels.unavailable}</p></section>
      {summary.owner_breakdown !== null && <section className="dashboard-breakdown" aria-label={labels.breakdown}><h2>{labels.breakdown}</h2>
        {summary.owner_breakdown.length === 0 && <p>{labels.noData}</p>}
        {summary.owner_breakdown.map((item) => {
          const member = members.items.find((candidate) => candidate.membership_id === item.owner_membership_id)
          const name = item.owner_membership_id === null ? labels.unassigned : member?.user.display_name ?? item.owner_membership_id
          return <details key={item.owner_membership_id ?? 'unassigned'}><summary>{name}</summary><SummarySections data={{ ...item, as_of: summary.as_of }} locale={locale} labels={labels} timezone={timezone} compact /></details>
        })}
      </section>}
    </>}
  </main>
}
