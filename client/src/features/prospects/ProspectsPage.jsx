import { useCallback, useEffect, useRef, useState } from 'react'

import { Building2, LoaderCircle, Search } from '../../icons'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { followInternalLink } from '../../app/navigation'
import { prospectApi } from './api/prospectApi'

const CREATE_PROSPECT_PATH = '/app/prospects/new'


function formatDate(value) {
  return new Intl.DateTimeFormat('fr-CA', { dateStyle: 'medium' }).format(new Date(value))
}


function OriginBadge({ origin }) {
  const labels = { manual: 'Saisie manuelle', google_place: 'Google Places', import: 'Import', connector: 'Connecteur', open_data: 'Donnée ouverte' }
  return <span className="prospect-origin">{labels[origin] ?? origin}</span>
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
  const requestRef = useRef(null)
  const canCreate = session.capabilities.includes('prospects:create')
  const canReadTasks = session.capabilities.includes('tasks:read')

  const load = useCallback(async ({ cursor = '', append = false } = {}) => {
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    if (append) setLoadingMore(true)
    else setLoading(true)
    setError('')
    try {
      const [result, actionPage] = await Promise.all([
        prospectApi.list({ cursor, includeArchived, searchText: submittedSearch }, controller.signal),
        canReadTasks ? prospectApi.listNextActions(controller.signal) : Promise.resolve({ items: [] }),
      ])
      const actionByProspect = Object.fromEntries((actionPage.items ?? []).map((task) => [task.prospect_id, task]))
      setNextActions((current) => append ? { ...current, ...actionByProspect } : actionByProspect)
      const items = (result.items ?? []).map((prospect) => ({ ...prospect, next_action: actionByProspect[prospect.id] ?? null }))
      setPage((current) => append
        ? { items: [...current.items, ...items], next_cursor: result.next_cursor }
        : { items, next_cursor: result.next_cursor })
    } catch (requestError) {
      if (requestError?.name !== 'AbortError') setError(toUserMessage(requestError, 'Impossible de charger les prospects.'))
    } finally {
      if (requestRef.current === controller) requestRef.current = null
      setLoading(false)
      setLoadingMore(false)
    }
  }, [canReadTasks, includeArchived, submittedSearch])

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
        <p className="eyebrow">Portefeuille CRM</p>
        <h1 id="prospects-title">Prospects</h1>
        <p>Suivez les établissements ajoutés à votre organisation. Les données affichées sont des informations CRM, distinctes des détails Google.</p>
      </div>
      {canCreate && <a className="primary-button" href={CREATE_PROSPECT_PATH} onClick={(event) => followInternalLink(event, CREATE_PROSPECT_PATH)}>Ajouter un prospect</a>}
    </header>

    <section className="prospect-list-card" aria-labelledby="prospect-list-title">
      <div className="prospect-list-toolbar">
        <form onSubmit={submitSearch} className="prospect-search-form">
          <label className="sr-only" htmlFor="prospect-search">Rechercher dans les prospects</label>
          <Search size={18} />
          <input id="prospect-search" value={searchText} onChange={(event) => setSearchText(event.target.value)} maxLength="255" placeholder="Rechercher un nom, Place ID, secteur ou une ville" />
          <button className="secondary-button" type="submit">Rechercher</button>
        </form>
        <label className="prospect-archive-filter"><input type="checkbox" checked={includeArchived} onChange={changeArchiveVisibility} /> Inclure les archivés</label>
      </div>

      {error && <ErrorBanner><span>{error}</span><button type="button" className="link-button" onClick={() => load()}>Réessayer</button></ErrorBanner>}
      <h2 id="prospect-list-title">Établissements suivis <span>{page.items.length}</span></h2>

      {loading ? <div className="administration-loading" role="status"><LoaderCircle className="spin" size={20} /> Chargement des prospects…</div> : page.items.length === 0 ? <div className="prospect-empty-state"><Building2 size={28} /><h3>Aucun prospect à afficher</h3><p>{submittedSearch ? 'Modifiez vos filtres ou effectuez une nouvelle recherche.' : 'Ajoutez un établissement depuis Google ou créez un prospect manuellement.'}</p></div> : <div className="prospect-list" role="list">
        {page.items.map((prospect) => <a className={`prospect-row ${prospect.archived_at ? 'archived' : ''}`} href={`/app/prospects/${encodeURIComponent(prospect.id)}`} onClick={(event) => followInternalLink(event, `/app/prospects/${encodeURIComponent(prospect.id)}`)} key={prospect.id} role="listitem">
          <div className="prospect-row-icon" aria-hidden="true"><Building2 size={19} /></div>
          <div className="prospect-row-main"><h3>{prospect.internal_alias}</h3><div><OriginBadge origin={prospect.origin} /> {prospect.google_place_id && <span className="prospect-place-id">Place ID&nbsp;: <code>{prospect.google_place_id}</code></span>} {prospect.industry_label && <span>{prospect.industry_label}</span>} {prospect.city && <span>{prospect.city}</span>}</div></div>
          <div className="prospect-row-meta"><span>Priorité {prospect.priority}/5</span>{nextActions[prospect.id] && <span className="next-action-summary">Prochaine action : {nextActions[prospect.id].title}</span>}<time dateTime={prospect.updated_at}>Mis à jour le {formatDate(prospect.updated_at)}</time>{prospect.archived_at && <strong>Archivé</strong>}</div>
        </a>)}
      </div>}

      {page.next_cursor && <button className="secondary-button prospect-load-more" type="button" onClick={() => load({ cursor: page.next_cursor, append: true })} disabled={loadingMore}>{loadingMore ? 'Chargement…' : 'Afficher davantage'}</button>}
    </section>
  </main>
}
