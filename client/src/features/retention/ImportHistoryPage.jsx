import { useCallback, useEffect, useState } from 'react'

import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { importHistoryApi } from './api/importHistoryApi'

const COPY = {
  'fr-CA': { title: 'Historique des imports', intro: 'Rapports conservés sans fichier CSV brut.', runs: 'Lots confirmés', sessions: 'Sessions', empty: 'Aucun import.', more: 'Voir plus', show: 'Voir le rapport', retry: 'Corriger avec un nouveau CSV', created: 'créés', duplicates: 'doublons', quarantined: 'quarantainés', review: 'dont à revoir', line: 'Ligne', reasons: 'Motifs', quarantine: 'Quarantaine', error: 'Impossible de charger l’historique.', filters: 'Filtres', from: 'Du', to: 'Au', declaration: 'Identifiant de déclaration', author: 'Identifiant du déclarant', status: 'Statut', apply: 'Appliquer' },
  'en-CA': { title: 'Import history', intro: 'Reports are retained without the raw CSV file.', runs: 'Confirmed runs', sessions: 'Sessions', empty: 'No imports yet.', more: 'Show more', retry: 'Correct with a new CSV', created: 'created', duplicates: 'duplicates', quarantined: 'quarantined', review: 'of which need review', line: 'Line', reasons: 'Reasons', quarantine: 'Quarantine', error: 'Could not load import history.', filters: 'Filters', from: 'From', to: 'To', declaration: 'Declaration ID', author: 'Declarant ID', status: 'Status', apply: 'Apply', show: 'View report' },
}

export function ImportHistoryPage({ session }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = COPY[locale]
  const [runs, setRuns] = useState([])
  const [sessions, setSessions] = useState([])
  const [runCursor, setRunCursor] = useState(null)
  const [sessionCursor, setSessionCursor] = useState(null)
  const [selected, setSelected] = useState(null)
  const [quarantine, setQuarantine] = useState([])
  const [quarantineCursor, setQuarantineCursor] = useState(null)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({})
  const loadRuns = useCallback(async (cursor = '') => {
    try { const runFilters = { ...filters }; delete runFilters.status; const page = await importHistoryApi.runs(cursor, runFilters); setRuns((current) => cursor ? [...current, ...page.items] : page.items); setRunCursor(page.next_cursor) }
    catch (cause) { setError(toUserMessage(cause, copy.error)) }
  }, [copy.error, filters])
  const loadSessions = useCallback(async (cursor = '') => {
    try { const page = await importHistoryApi.sessions(cursor, filters); setSessions((current) => cursor ? [...current, ...page.items] : page.items); setSessionCursor(page.next_cursor) }
    catch (cause) { setError(toUserMessage(cause, copy.error)) }
  }, [copy.error, filters])
  useEffect(() => { loadRuns(); loadSessions() }, [loadRuns, loadSessions])
  async function selectRun(id) {
    try { const [run, page] = await Promise.all([importHistoryApi.run(id), importHistoryApi.quarantines(id)]); setSelected(run); setQuarantine(page.items); setQuarantineCursor(page.next_cursor); setError('') }
    catch (cause) { setError(toUserMessage(cause, copy.error)) }
  }
  async function moreQuarantine() {
    try { const page = await importHistoryApi.quarantines(selected.id, quarantineCursor); setQuarantine((current) => [...current, ...page.items]); setQuarantineCursor(page.next_cursor) }
    catch (cause) { setError(toUserMessage(cause, copy.error)) }
  }
  function applyFilters(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const next = Object.fromEntries(['created_from', 'created_to', 'declaration_id', 'author_id', 'status'].map((key) => [key, String(form.get(key) ?? '').trim()]).filter(([, value]) => value))
    for (const key of ['created_from', 'created_to']) if (next[key]) next[key] = new Date(next[key]).toISOString()
    setFilters(next)
    setSelected(null)
  }
  return <main className="administration-page" aria-labelledby="import-history-title">
    <header className="administration-page-heading"><h1 id="import-history-title">{copy.title}</h1><p>{copy.intro}</p></header>
    {error && <ErrorBanner>{error}</ErrorBanner>}
    <section className="administration-card compliance-form-card"><h2>{copy.filters}</h2><form className="compliance-form" onSubmit={applyFilters}>
      <label>{copy.from}<input type="datetime-local" name="created_from" /></label><label>{copy.to}<input type="datetime-local" name="created_to" /></label>
      <label>{copy.declaration}<input name="declaration_id" /></label><label>{copy.author}<input name="author_id" /></label>
      <label>{copy.status}<select name="status"><option value="">—</option>{['uploaded', 'mapped', 'validated', 'confirmed', 'expired'].map((status) => <option key={status} value={status}>{status}</option>)}</select></label>
      <button className="primary-button">{copy.apply}</button>
    </form></section>
    <section className="administration-card"><h2>{copy.runs}</h2>{runs.length ? <ul className="compliance-list">{runs.map((run) => <li key={run.id}><div><strong>{new Date(run.completed_at).toLocaleString(locale)}</strong><small>{run.created_count} {copy.created} · {run.duplicate_count} {copy.duplicates} · {run.quarantined_count} {copy.quarantined} ({run.review_count} {copy.review})</small></div><button type="button" className="secondary-button" onClick={() => selectRun(run.id)}>{copy.show}</button></li>)}</ul> : <p>{copy.empty}</p>}{runCursor && <button type="button" className="secondary-button" onClick={() => loadRuns(runCursor)}>{copy.more}</button>}</section>
    {selected && <section className="administration-card" aria-live="polite"><h2>{copy.show}</h2><p>{selected.created_count} {copy.created} · {selected.duplicate_count} {copy.duplicates} · {selected.quarantined_count} {copy.quarantined} ({selected.review_count} {copy.review})</p>
      {session.capabilities.includes('imports:retry') && <a className="secondary-button" href={`/app/compliance/retention?retry_of_run_id=${encodeURIComponent(selected.id)}`}>{copy.retry}</a>}
      <h3>{copy.quarantine}</h3>{quarantine.length ? <ul className="compliance-list">{quarantine.map((item) => <li key={item.line_number}><strong>{copy.line} {item.line_number}</strong><small>{copy.reasons}: {item.reason_codes.join(', ')}</small><small>{item.opaque_reference}</small></li>)}</ul> : <p>{copy.empty}</p>}
      {quarantineCursor && <button type="button" className="secondary-button" onClick={moreQuarantine}>{copy.more}</button>}
    </section>}
    <section className="administration-card"><h2>{copy.sessions}</h2>{sessions.length ? <ul className="compliance-list">{sessions.map((item) => <li key={item.id}><strong>{new Date(item.created_at).toLocaleString(locale)}</strong><small>{item.status} · {item.row_count ?? 0} {locale === 'fr-CA' ? 'lignes' : 'rows'}</small></li>)}</ul> : <p>{copy.empty}</p>}{sessionCursor && <button type="button" className="secondary-button" onClick={() => loadSessions(sessionCursor)}>{copy.more}</button>}</section>
  </main>
}
