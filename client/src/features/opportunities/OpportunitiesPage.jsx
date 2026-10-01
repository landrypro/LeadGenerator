import { useCallback, useEffect, useRef, useState } from 'react'

import { Building2, LoaderCircle, Search } from '../../icons'
import { followInternalLink } from '../../app/navigation'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { opportunityApi } from './api/opportunityApi'
import { getOpportunityMessages } from './opportunityMessages'
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
  const strings = getOpportunityMessages(locale)

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
      if (requestError?.name !== 'AbortError') setError(toUserMessage(requestError, strings.loadError))
    } finally {
      if (requestRef.current === controller) requestRef.current = null
      setLoading(false); setLoadingMore(false)
    }
  }, [currency, overdue, stage, strings.loadError, submittedSearch])

  useEffect(() => { load(); return () => requestRef.current?.abort() }, [load])

  return <main className="administration-page opportunities-page" aria-labelledby="opportunities-title">
    <header className="administration-page-heading"><p className="eyebrow">{strings.portfolioEyebrow}</p><h1 id="opportunities-title">{strings.title}</h1><p>{strings.portfolioDescription}</p></header>
    <form className="opportunity-filters" onSubmit={(event) => { event.preventDefault(); setSubmittedSearch(search) }}>
      <label className="sr-only" htmlFor="opportunity-search">{strings.searchLabel}</label><Search size={18} /><input id="opportunity-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={strings.searchPlaceholder} />
      <select aria-label={strings.stage} value={stage} onChange={(event) => setStage(event.target.value)}><option value="">{strings.allStages}</option>{OPPORTUNITY_STAGES.map(([code]) => <option key={code} value={code}>{stageLabel(code, locale)}</option>)}</select>
      <input aria-label={strings.currency} value={currency} maxLength="3" placeholder={strings.currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} />
      <label><input type="checkbox" checked={overdue} onChange={(event) => setOverdue(event.target.checked)} /> {strings.overdue}</label><button className="secondary-button" type="submit">{strings.filter}</button>
    </form>
    {error && <ErrorBanner><span>{error}</span><button type="button" className="link-button" onClick={() => load()}>{strings.retry}</button></ErrorBanner>}
    {page.aggregates_by_currency?.length > 0 && <section className="opportunity-portfolio-summary" aria-label={strings.totalsByCurrency}>{page.aggregates_by_currency.map((aggregate) => <div key={aggregate.currency_code}><strong>{formatMoney(aggregate.amount_total, aggregate.currency_code, locale)}</strong><span>{formatMoney(aggregate.weighted_amount_total, aggregate.currency_code, locale)} {strings.weighted}</span></div>)}</section>}
    {loading ? <div className="administration-loading" role="status"><LoaderCircle className="spin" size={20} /> {strings.loading}</div> : <section className="opportunity-portfolio-list" aria-label={strings.listLabel}>{page.items?.length ? page.items.map((item) => <article key={item.id} className="opportunity-portfolio-card"><div><h2>{item.name}</h2><a href={`/app/prospects/${encodeURIComponent(item.prospect_id)}`} onClick={(event) => followInternalLink(event, `/app/prospects/${encodeURIComponent(item.prospect_id)}`)}><Building2 size={15} /> {strings.viewProspect}</a></div><dl><div><dt>{strings.stage}</dt><dd>{stageLabel(item.stage_code, locale)}</dd></div><div><dt>{strings.amount}</dt><dd>{formatMoney(item.amount, item.currency_code, locale)}</dd></div><div><dt>{strings.weightedValue}</dt><dd>{formatMoney(item.weighted_amount, item.currency_code, locale)}</dd></div><div><dt>{strings.dueDate}</dt><dd>{formatDate(item.expected_close_on, locale)}{item.overdue ? ` · ${strings.overdue}` : ''}</dd></div></dl></article>) : <p className="form-help">{strings.noFilterResults}</p>}</section>}
    {page.next_cursor && <button type="button" className="secondary-button prospect-load-more" disabled={loadingMore} onClick={() => load({ cursor: page.next_cursor, append: true })}>{loadingMore ? strings.loadingMore : strings.loadMore}</button>}
  </main>
}
