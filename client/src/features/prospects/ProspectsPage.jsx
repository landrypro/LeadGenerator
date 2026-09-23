import { useCallback, useEffect, useRef, useState } from 'react'

import { Building2, LoaderCircle, Search } from '../../icons'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { followInternalLink } from '../../app/navigation'
import { prospectApi } from './api/prospectApi'
import { opportunityApi } from '../opportunities/api/opportunityApi'
import { formatMoney } from '../opportunities/opportunityPresentation'

const CREATE_PROSPECT_PATH = '/app/prospects/new'


const PROSPECTS_MESSAGES = Object.freeze({
  'fr-CA': Object.freeze({ eyebrow: 'Portefeuille CRM', description: 'Suivez les établissements ajoutés à votre organisation. Les données affichées sont des informations CRM, distinctes des détails Google.', add: 'Ajouter un prospect', searchLabel: 'Rechercher dans les prospects', searchPlaceholder: 'Rechercher un nom, Place ID, secteur ou une ville', search: 'Rechercher', includeArchived: 'Inclure les archivés', retry: 'Réessayer', tracked: 'Établissements suivis', loading: 'Chargement des prospects…', empty: 'Aucun prospect à afficher', emptySearch: 'Modifiez vos filtres ou effectuez une nouvelle recherche.', emptyDefault: 'Ajoutez un établissement depuis Google ou créez un prospect manuellement.', priority: 'Priorité', nextAction: 'Prochaine action', openOpportunities: 'opportunité(s) ouverte(s)', updated: 'Mis à jour le', archived: 'Archivé', loadingMore: 'Chargement…', loadMore: 'Afficher davantage', loadError: 'Impossible de charger les prospects.', origins: Object.freeze({ manual: 'Saisie manuelle', google_place: 'Google Places', import: 'Import', connector: 'Connecteur', open_data: 'Donnée ouverte' }) }),
  'en-CA': Object.freeze({ eyebrow: 'CRM portfolio', description: 'Track businesses added to your organization. The data shown is CRM information, separate from Google details.', add: 'Add a prospect', searchLabel: 'Search prospects', searchPlaceholder: 'Search by name, Place ID, industry, or city', search: 'Search', includeArchived: 'Include archived', retry: 'Try again', tracked: 'Tracked businesses', loading: 'Loading prospects…', empty: 'No prospects to display', emptySearch: 'Change your filters or run a new search.', emptyDefault: 'Add a business from Google or create a prospect manually.', priority: 'Priority', nextAction: 'Next action', openOpportunities: 'open opportunity(ies)', updated: 'Updated', archived: 'Archived', loadingMore: 'Loading…', loadMore: 'Show more', loadError: 'Unable to load prospects.', origins: Object.freeze({ manual: 'Manual entry', google_place: 'Google Places', import: 'Import', connector: 'Connector', open_data: 'Open data' }) }),
})

function formatDate(value, locale) {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(new Date(value))
}


function OriginBadge({ origin, copy }) {
  return <span className="prospect-origin">{copy.origins[origin] ?? origin}</span>
}


export function ProspectsPage({ session }) {
  const [page, setPage] = useState({ items: [], next_cursor: null })
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [searchText, setSearchText] = useState('')
  const [submittedSearch, setSubmittedSearch] = useState('')
  const [includeArchived, setIncludeArchived] = useState(false)
  const [nextActions, setNextActions] = useState({})
  const [opportunitySummaries, setOpportunitySummaries] = useState({})
  const requestRef = useRef(null)
  const locale = session.active_organization?.locale ?? 'fr-CA'
  const copy = PROSPECTS_MESSAGES[locale] ?? PROSPECTS_MESSAGES['fr-CA']
  const canCreate = session.capabilities.includes('prospects:create')
  const canReadTasks = session.capabilities.includes('tasks:read')
  const canReadOpportunities = session.capabilities.includes('opportunities:read')

  const load = useCallback(async ({ cursor = '', append = false } = {}) => {
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    if (append) setLoadingMore(true)
    else setLoading(true)
    setError('')
    try {
      const result = await prospectApi.list({ cursor, includeArchived, searchText: submittedSearch }, controller.signal)
      const [actionPage, summariesPage] = await Promise.all([
        canReadTasks ? prospectApi.listNextActions(controller.signal) : Promise.resolve({ items: [] }),
        canReadOpportunities ? opportunityApi.summaries((result.items ?? []).map((item) => item.id), controller.signal) : Promise.resolve({ items: [] }),
      ])
      const actionByProspect = Object.fromEntries((actionPage.items ?? []).map((task) => [task.prospect_id, task]))
      const summariesByProspect = Object.fromEntries((summariesPage.items ?? []).map((summary) => [summary.prospect_id, summary]))
      setNextActions((current) => append ? { ...current, ...actionByProspect } : actionByProspect)
      setOpportunitySummaries((current) => append ? { ...current, ...summariesByProspect } : summariesByProspect)
      const items = (result.items ?? []).map((prospect) => ({ ...prospect, next_action: actionByProspect[prospect.id] ?? null }))
      setPage((current) => append
        ? { items: [...current.items, ...items], next_cursor: result.next_cursor }
        : { items, next_cursor: result.next_cursor })
    } catch (requestError) {
      if (requestError?.name !== 'AbortError') setError(toUserMessage(requestError, copy.loadError))
    } finally {
      if (requestRef.current === controller) requestRef.current = null
      setLoading(false)
      setLoadingMore(false)
    }
  }, [canReadOpportunities, canReadTasks, copy.loadError, includeArchived, submittedSearch])

  useEffect(() => {
    load()
    return () => requestRef.current?.abort()
  }, [load])

  function submitSearch(event) {
    event.preventDefault()
    setSubmittedSearch(searchText)
  }

  function changeArchiveVisibility(event) {
    setIncludeArchived(event.target.checked)
  }

  return <main className="administration-page prospects-page" aria-labelledby="prospects-title">
    <header className="administration-page-heading prospects-heading">
      <div>
        <p className="eyebrow">{copy.eyebrow}</p>
        <h1 id="prospects-title">Prospects</h1>
        <p>{copy.description}</p>
      </div>
      {canCreate && <a className="primary-button" href={CREATE_PROSPECT_PATH} onClick={(event) => followInternalLink(event, CREATE_PROSPECT_PATH)}>{copy.add}</a>}
    </header>

    <section className="prospect-list-card" aria-labelledby="prospect-list-title">
      <div className="prospect-list-toolbar">
        <form onSubmit={submitSearch} className="prospect-search-form">
          <label className="sr-only" htmlFor="prospect-search">{copy.searchLabel}</label>
          <Search size={18} />
          <input id="prospect-search" value={searchText} onChange={(event) => setSearchText(event.target.value)} maxLength="255" placeholder={copy.searchPlaceholder} />
          <button className="secondary-button" type="submit">{copy.search}</button>
        </form>
        <label className="prospect-archive-filter"><input type="checkbox" checked={includeArchived} onChange={changeArchiveVisibility} /> {copy.includeArchived}</label>
      </div>

      {error && <ErrorBanner><span>{error}</span><button type="button" className="link-button" onClick={() => load()}>{copy.retry}</button></ErrorBanner>}
      <h2 id="prospect-list-title">{copy.tracked} <span>{page.items.length}</span></h2>

      {loading ? <div className="administration-loading" role="status"><LoaderCircle className="spin" size={20} /> {copy.loading}</div> : page.items.length === 0 ? <div className="prospect-empty-state"><Building2 size={28} /><h3>{copy.empty}</h3><p>{submittedSearch ? copy.emptySearch : copy.emptyDefault}</p></div> : <div className="prospect-list" role="list">
        {page.items.map((prospect) => <a className={`prospect-row ${prospect.archived_at ? 'archived' : ''}`} href={`/app/prospects/${encodeURIComponent(prospect.id)}`} onClick={(event) => followInternalLink(event, `/app/prospects/${encodeURIComponent(prospect.id)}`)} key={prospect.id} role="listitem">
          <div className="prospect-row-icon" aria-hidden="true"><Building2 size={19} /></div>
          <div className="prospect-row-main"><h3>{prospect.internal_alias}</h3><div><OriginBadge origin={prospect.origin} copy={copy} /> {prospect.google_place_id && <span className="prospect-place-id">Place ID&nbsp;: <code>{prospect.google_place_id}</code></span>} {prospect.industry_label && <span>{prospect.industry_label}</span>} {prospect.city && <span>{prospect.city}</span>}</div></div>
          <div className="prospect-row-meta"><span>{copy.priority} {prospect.priority}/5</span>{nextActions[prospect.id] && <span className="next-action-summary">{copy.nextAction}: {nextActions[prospect.id].title}</span>}{opportunitySummaries[prospect.id] && <span className="next-action-summary">{opportunitySummaries[prospect.id].open_count} {copy.openOpportunities} · {opportunitySummaries[prospect.id].aggregates_by_currency.map((aggregate) => formatMoney(aggregate.weighted_amount_total, aggregate.currency_code, locale)).join(' · ')}</span>}<time dateTime={prospect.updated_at}>{copy.updated} {formatDate(prospect.updated_at, locale)}</time>{prospect.archived_at && <strong>{copy.archived}</strong>}</div>
        </a>)}
      </div>}

      {page.next_cursor && <button className="secondary-button prospect-load-more" type="button" onClick={() => load({ cursor: page.next_cursor, append: true })} disabled={loadingMore}>{loadingMore ? copy.loadingMore : copy.loadMore}</button>}
    </section>
  </main>
}
