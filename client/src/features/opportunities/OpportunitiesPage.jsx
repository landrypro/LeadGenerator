import { useCallback, useEffect, useRef, useState } from 'react'

import { Building2, LoaderCircle, Search } from '../../icons'
import { followInternalLink } from '../../app/navigation'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { opportunityApi } from './api/opportunityApi'
import { formatDate, formatMoney, OPPORTUNITY_STAGES, stageLabel } from './opportunityPresentation'

export function OpportunitiesPage({ session }) {
  const [page, setPage] = useState({ items: [], next_cursor: null, aggregates_by_currency: [] })
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [submittedSearch, setSubmittedSearch] = useState('')
  const [stage, setStage] = useState('')
  const [currency, setCurrency] = useState('')
  const [overdue, setOverdue] = useState(false)
  const requestRef = useRef(null)
  const locale = session.active_organization?.locale ?? 'fr-CA'

  const load = useCallback(async ({ cursor = '', append = false } = {}) => {
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    if (append) setLoadingMore(true); else setLoading(true)
    setError('')
    try {
      const result = await opportunityApi.list({ cursor, q: submittedSearch, stages: stage ? [stage] : [], currencyCode: currency, overdue }, controller.signal)
      setPage((current) => append ? { ...result, items: [...current.items, ...(result.items ?? [])] } : result)
    } catch (requestError) {
      if (requestError?.name !== 'AbortError') setError(toUserMessage(requestError, 'Impossible de charger les opportunités.'))
    } finally {
      if (requestRef.current === controller) requestRef.current = null
      setLoading(false); setLoadingMore(false)
    }
  }, [currency, overdue, stage, submittedSearch])

  useEffect(() => { load(); return () => requestRef.current?.abort() }, [load])

  return <main className="administration-page opportunities-page" aria-labelledby="opportunities-title">
    <header className="administration-page-heading"><p className="eyebrow">Portefeuille CRM</p><h1 id="opportunities-title">Opportunités</h1><p>Suivez les montants, les échéances et la progression commerciale sans mélange de devises.</p></header>
    <form className="opportunity-filters" onSubmit={(event) => { event.preventDefault(); setSubmittedSearch(search) }}>
      <label className="sr-only" htmlFor="opportunity-search">Rechercher une opportunité</label><Search size={18} /><input id="opportunity-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Rechercher une opportunité ou un prospect" />
      <select aria-label="Étape" value={stage} onChange={(event) => setStage(event.target.value)}><option value="">Toutes les étapes</option>{OPPORTUNITY_STAGES.map(([code]) => <option key={code} value={code}>{stageLabel(code, locale)}</option>)}</select>
      <input aria-label="Devise" value={currency} maxLength="3" placeholder="Devise" onChange={(event) => setCurrency(event.target.value.toUpperCase())} />
      <label><input type="checkbox" checked={overdue} onChange={(event) => setOverdue(event.target.checked)} /> En retard</label><button className="secondary-button" type="submit">Filtrer</button>
    </form>
    {error && <ErrorBanner><span>{error}</span><button type="button" className="link-button" onClick={() => load()}>Réessayer</button></ErrorBanner>}
    {page.aggregates_by_currency?.length > 0 && <section className="opportunity-portfolio-summary" aria-label="Totaux par devise">{page.aggregates_by_currency.map((aggregate) => <div key={aggregate.currency_code}><strong>{formatMoney(aggregate.amount_total, aggregate.currency_code, locale)}</strong><span>{formatMoney(aggregate.weighted_amount_total, aggregate.currency_code, locale)} pondéré</span></div>)}</section>}
    {loading ? <div className="administration-loading" role="status"><LoaderCircle className="spin" size={20} /> Chargement des opportunités…</div> : <section className="opportunity-portfolio-list" aria-label="Liste des opportunités">{page.items?.length ? page.items.map((item) => <article key={item.id} className="opportunity-portfolio-card"><div><h2>{item.name}</h2><a href={`/app/prospects/${encodeURIComponent(item.prospect_id)}`} onClick={(event) => followInternalLink(event, `/app/prospects/${encodeURIComponent(item.prospect_id)}`)}><Building2 size={15} /> Voir le prospect</a></div><dl><div><dt>Étape</dt><dd>{stageLabel(item.stage_code, locale)}</dd></div><div><dt>Montant</dt><dd>{formatMoney(item.amount, item.currency_code, locale)}</dd></div><div><dt>Valeur pondérée</dt><dd>{formatMoney(item.weighted_amount, item.currency_code, locale)}</dd></div><div><dt>Échéance</dt><dd>{formatDate(item.expected_close_on, locale)}{item.overdue ? ' · En retard' : ''}</dd></div></dl></article>) : <p className="form-help">Aucune opportunité ne correspond aux filtres.</p>}</section>}
    {page.next_cursor && <button type="button" className="secondary-button prospect-load-more" disabled={loadingMore} onClick={() => load({ cursor: page.next_cursor, append: true })}>{loadingMore ? 'Chargement…' : 'Charger plus'}</button>}
  </main>
}
