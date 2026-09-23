import { useCallback, useEffect, useRef, useState } from 'react'

import { Building2, LoaderCircle, Search } from '../../icons'
import { followInternalLink } from '../../app/navigation'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { createRequestId } from '../../shared/ids/requestId'
import { prospectApi } from './api/prospectApi'
import { opportunityApi } from '../opportunities/api/opportunityApi'
import { formatMoney } from '../opportunities/opportunityPresentation'


function stageLabel(stage, locale) {
  return stage.labels?.[locale] ?? stage.labels?.['fr-CA'] ?? stage.labels?.['en-CA'] ?? stage.code
}

const reopenReasons = [
  { value: 'customer_reengaged', label: 'Le prospect a repris contact' },
  { value: 'additional_information', label: 'De nouvelles informations justifient la reprise' },
  { value: 'entered_in_error', label: 'Le statut a été attribué par erreur' },
  { value: 'other', label: 'Autre motif' },
]

const lossReasons = [
  { value: 'no_need', label: 'Le besoin ne correspond pas à notre offre' },
  { value: 'no_budget', label: 'Le budget n’est pas disponible' },
  { value: 'no_response', label: 'Aucun retour après les relances' },
  { value: 'competitor', label: 'Une offre concurrente a été retenue' },
  { value: 'timing', label: 'Le projet est reporté ou le moment n’est pas opportun' },
  { value: 'outside_territory', label: 'Le prospect est hors de notre zone de couverture' },
  { value: 'invalid_or_duplicate', label: 'Le prospect est invalide ou en double' },
  { value: 'other', label: 'Autre motif' },
]


export function PipelinePage({ session }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = locale === 'en-CA' ? {
    eyebrow: 'CRM portfolio', title: 'Sales pipeline', description: 'Follow prospects by stage. Every move is controlled and recorded in the activity log.', filter: 'Filter pipeline', filterPlaceholder: 'Filter by name, business type, or city', apply: 'Filter', retry: 'Try again', loading: 'Loading pipeline…', priority: 'Priority', nextAction: 'Next action:', openOpportunities: 'open opportunity(s)', markLost: 'Mark as lost', reopen: 'Reopen', loadingMore: 'Loading…', loadMore: 'Load more', lossTitle: 'Mark prospect as lost', lossHelp: 'Select the business reason that explains why follow-up is stopping.', lossReason: 'Loss reason', reopenTitle: 'Reopen prospect', reopenHelp: 'Select the business reason that explains resuming follow-up.', reopenReason: 'Reopening reason', specify: 'Specify reason', cancel: 'Cancel', confirmingLoss: 'Updating…', confirmLoss: 'Confirm loss', reopening: 'Reopening…', confirmReopen: 'Confirm reopening', lossRequired: 'Specify the loss reason.', reopenRequired: 'Specify the reopening reason.', pipelineError: 'Unable to load the pipeline.', moveError: 'Unable to move the prospect.', moreError: 'Unable to load more prospects.', reopenError: 'Unable to reopen the prospect.', lostReasons: ['The need does not match our offer', 'The budget is unavailable', 'No response after follow-ups', 'A competitor was selected', 'The project is postponed or timing is not right', 'The prospect is outside our coverage area', 'The prospect is invalid or duplicated', 'Other reason'], reopenReasons: ['The prospect got back in touch', 'New information justifies resuming', 'The status was assigned in error', 'Other reason']
  } : {
    eyebrow: 'Portefeuille CRM', title: 'Pipeline commercial', description: 'Suivez les prospects par étape. Chaque déplacement est contrôlé et inscrit au journal d’activité.', filter: 'Filtrer le pipeline', filterPlaceholder: 'Filtrer un nom, un secteur ou une ville', apply: 'Filtrer', retry: 'Réessayer', loading: 'Chargement du pipeline…', priority: 'Priorité', nextAction: 'Prochaine action :', openOpportunities: 'opportunité(s) ouverte(s)', markLost: 'Marquer perdu', reopen: 'Réouvrir', loadingMore: 'Chargement…', loadMore: 'Charger plus', lossTitle: 'Marquer le prospect comme perdu', lossHelp: 'Choisissez le motif commercial qui explique l’arrêt du suivi.', lossReason: 'Motif de perte', reopenTitle: 'Réouvrir le prospect', reopenHelp: 'Choisissez le motif commercial qui explique la reprise du suivi.', reopenReason: 'Motif de réouverture', specify: 'Précisez le motif', cancel: 'Annuler', confirmingLoss: 'Mise à jour…', confirmLoss: 'Confirmer la perte', reopening: 'Réouverture…', confirmReopen: 'Confirmer la réouverture', lossRequired: 'Précisez le motif de perte.', reopenRequired: 'Précisez le motif de réouverture.', pipelineError: 'Impossible de charger le pipeline.', moveError: 'Impossible de déplacer le prospect.', moreError: 'Impossible de charger davantage de prospects.', reopenError: 'Impossible de réouvrir le prospect.', lostReasons: lossReasons.map((reason) => reason.label), reopenReasons: reopenReasons.map((reason) => reason.label)
  }
  const [board, setBoard] = useState({ stages: [], columns: {}, next_cursors: {} })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchText, setSearchText] = useState('')
  const [submittedSearch, setSubmittedSearch] = useState('')
  const [moving, setMoving] = useState('')
  const [loadingColumns, setLoadingColumns] = useState({})
  const [reopenIntent, setReopenIntent] = useState(null)
  const [reopenReasonCode, setReopenReasonCode] = useState('customer_reengaged')
  const [reopenReasonNote, setReopenReasonNote] = useState('')
  const [reopenFormError, setReopenFormError] = useState('')
  const [lossIntent, setLossIntent] = useState(null)
  const [lossReasonCode, setLossReasonCode] = useState('no_need')
  const [lossReasonNote, setLossReasonNote] = useState('')
  const [lossFormError, setLossFormError] = useState('')
  const [nextActions, setNextActions] = useState({})
  const [opportunitySummaries, setOpportunitySummaries] = useState({})
  const requestRef = useRef(null)
  const canMove = session.capabilities.includes('pipeline:move')
  const canReopen = session.capabilities.includes('pipeline:reopen')
  const canReadTasks = session.capabilities.includes('tasks:read')
  const canReadOpportunities = session.capabilities.includes('opportunities:read')

  const load = useCallback(async () => {
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setLoading(true)
    setError('')
    try {
      const nextBoard = await prospectApi.pipelineBoard({ searchText: submittedSearch }, controller.signal)
      const prospectIds = Object.values(nextBoard.columns ?? {}).flat().map((prospect) => prospect.id)
      const [actionPage, summariesPage] = await Promise.all([
        canReadTasks ? prospectApi.listNextActions(controller.signal) : Promise.resolve({ items: [] }),
        canReadOpportunities ? opportunityApi.summaries(prospectIds, controller.signal) : Promise.resolve({ items: [] }),
      ])
      setNextActions(Object.fromEntries((actionPage.items ?? []).map((task) => [task.prospect_id, task])))
      setOpportunitySummaries(Object.fromEntries((summariesPage.items ?? []).map((summary) => [summary.prospect_id, summary])))
      setBoard(nextBoard)
    } catch (requestError) {
      if (requestError?.name !== 'AbortError') setError(toUserMessage(requestError, copy.pipelineError))
    } finally {
      if (requestRef.current === controller) requestRef.current = null
      setLoading(false)
    }
  }, [canReadOpportunities, canReadTasks, copy.pipelineError, submittedSearch])

  useEffect(() => {
    load()
    return () => requestRef.current?.abort()
  }, [load])

  async function move(prospect, stage) {
    if (!canMove || moving) return
    if (stage.code === 'lost') {
      requestLoss(prospect, stage)
      return
    }
    await performMove(prospect, stage)
  }

  async function performMove(prospect, stage, reasonCode, reasonNote) {
    setMoving(prospect.id)
    setError('')
    try {
      await prospectApi.moveStage(prospect.id, {
        version: prospect.version, to_stage: stage.code, reason_code: reasonCode || undefined,
        reason_note: reasonNote || undefined, idempotency_key: createRequestId(),
      })
      await load()
    } catch (requestError) {
      setError(toUserMessage(requestError, copy.moveError))
    } finally {
      setMoving('')
    }
  }

  async function loadMore(stageCode) {
    const cursor = board.next_cursors?.[stageCode]
    const displayed = board.columns?.[stageCode] ?? []
    if (!cursor || displayed.length >= 50 || loadingColumns[stageCode]) return
    setLoadingColumns((current) => ({ ...current, [stageCode]: true }))
    setError('')
    try {
      const page = await prospectApi.pipelineColumn(stageCode, { cursor, searchText: submittedSearch })
      setBoard((current) => {
        const existing = current.columns?.[stageCode] ?? []
        const additions = (page.items ?? []).filter((item) => !existing.some((candidate) => candidate.id === item.id))
        return {
          ...current,
          columns: { ...current.columns, [stageCode]: [...existing, ...additions].slice(0, 50) },
          next_cursors: { ...current.next_cursors, [stageCode]: page.next_cursor },
        }
      })
    } catch (requestError) {
      setError(toUserMessage(requestError, copy.moreError))
    } finally {
      setLoadingColumns((current) => ({ ...current, [stageCode]: false }))
    }
  }

  function requestLoss(prospect, stage) {
    setLossIntent({ prospect, stage })
    setLossReasonCode('no_need')
    setLossReasonNote('')
    setLossFormError('')
  }

  function closeLossDialog() {
    if (moving) return
    setLossIntent(null)
    setLossFormError('')
  }

  async function confirmLoss(event) {
    event.preventDefault()
    if (!lossIntent || moving) return
    const reasonNote = lossReasonNote.trim()
    if (lossReasonCode === 'other' && !reasonNote) {
      setLossFormError(copy.lossRequired)
      return
    }
    await performMove(lossIntent.prospect, lossIntent.stage, lossReasonCode, reasonNote || undefined)
    setLossIntent(null)
  }

  function requestReopen(prospect) {
    if (!canReopen || moving) return
    setReopenIntent(prospect)
    setReopenReasonCode('customer_reengaged')
    setReopenReasonNote('')
    setReopenFormError('')
  }

  function closeReopenDialog() {
    if (moving) return
    setReopenIntent(null)
    setReopenFormError('')
  }

  async function reopen(event) {
    event.preventDefault()
    if (!reopenIntent || moving) return
    const reasonNote = reopenReasonNote.trim()
    if (reopenReasonCode === 'other' && !reasonNote) {
      setReopenFormError(copy.reopenRequired)
      return
    }
    setMoving(reopenIntent.id)
    setError('')
    try {
      await prospectApi.reopen(reopenIntent.id, {
        version: reopenIntent.version,
        reason_code: reopenReasonCode,
        reason_note: reasonNote || undefined,
        idempotency_key: createRequestId(),
      })
      setReopenIntent(null)
      await load()
    } catch (requestError) {
      setError(toUserMessage(requestError, copy.reopenError))
    } finally {
      setMoving('')
    }
  }

  function submit(event) {
    event.preventDefault()
    setSubmittedSearch(searchText)
  }

  return <main className="administration-page pipeline-page" aria-labelledby="pipeline-title">
    <header className="administration-page-heading prospects-heading">
      <div><p className="eyebrow">{copy.eyebrow}</p><h1 id="pipeline-title">{copy.title}</h1><p>{copy.description}</p></div>
    </header>
    <form onSubmit={submit} className="prospect-search-form pipeline-search"><label className="sr-only" htmlFor="pipeline-search">{copy.filter}</label><Search size={18} /><input id="pipeline-search" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder={copy.filterPlaceholder} /><button className="secondary-button" type="submit">{copy.apply}</button></form>
    {error && <ErrorBanner><span>{error}</span><button className="link-button" type="button" onClick={load}>{copy.retry}</button></ErrorBanner>}
    {loading ? <div className="administration-loading" role="status"><LoaderCircle className="spin" size={20} /> {copy.loading}</div> : <section className="pipeline-board" aria-label={copy.title}>
      {board.stages.map((stage, index) => <section className={`pipeline-column pipeline-${stage.color_token}`} key={stage.code} aria-labelledby={`stage-${stage.code}`}>
        <header><h2 id={`stage-${stage.code}`}>{stageLabel(stage, locale)}</h2><span>{(board.columns?.[stage.code] ?? []).length}</span></header>
        <div className="pipeline-cards">{(board.columns?.[stage.code] ?? []).map((prospect) => <article className="pipeline-card" key={prospect.id}>
          <a href={`/app/prospects/${encodeURIComponent(prospect.id)}`} onClick={(event) => followInternalLink(event, `/app/prospects/${encodeURIComponent(prospect.id)}`)}><Building2 size={16} /><strong>{prospect.internal_alias}</strong></a>
          <small>{copy.priority} {prospect.priority}/5</small>
          {nextActions[prospect.id] && <small className="next-action-summary">{`${copy.nextAction} ${nextActions[prospect.id].title}`}</small>}
          {opportunitySummaries[prospect.id] && <small className="next-action-summary">{opportunitySummaries[prospect.id].open_count} {copy.openOpportunities} · {opportunitySummaries[prospect.id].aggregates_by_currency.map((aggregate) => formatMoney(aggregate.weighted_amount_total, aggregate.currency_code, locale)).join(' · ')}</small>}
          {canMove && stage.code !== 'lost' && stage.code !== 'won' && <div className="pipeline-move-actions">
            {index > 0 && <button type="button" disabled={moving === prospect.id} onClick={() => move(prospect, board.stages[index - 1])}>← {stageLabel(board.stages[index - 1], locale)}</button>}
            {index < board.stages.length - 1 && <button type="button" disabled={moving === prospect.id} onClick={() => move(prospect, board.stages[index + 1])}>{stageLabel(board.stages[index + 1], locale)} →</button>}
            <button type="button" disabled={moving === prospect.id} onClick={() => move(prospect, board.stages.find((candidate) => candidate.code === 'lost'))}>{copy.markLost}</button>
          </div>}
          {canReopen && (stage.code === 'lost' || stage.code === 'won') && <div className="pipeline-move-actions"><button type="button" disabled={moving === prospect.id} onClick={() => requestReopen(prospect)}>{copy.reopen}</button></div>}
        </article>)}</div>
        {board.next_cursors?.[stage.code] && (board.columns?.[stage.code] ?? []).length < 50 && <button className="secondary-button pipeline-load-more" type="button" disabled={loadingColumns[stage.code]} onClick={() => loadMore(stage.code)}>{loadingColumns[stage.code] ? copy.loadingMore : copy.loadMore}</button>}
      </section>)}
    </section>}
    {reopenIntent && <div className="confirmation-overlay" onMouseDown={closeReopenDialog}>
      <section className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="reopen-prospect-title" onMouseDown={(event) => event.stopPropagation()}>
        <h2 id="reopen-prospect-title">{copy.reopenTitle}</h2>
        <p>{copy.reopenHelp}</p>
        <form className="status-operation-form" onSubmit={reopen}>
          <label htmlFor="reopen-reason">{copy.reopenReason}</label>
          <select id="reopen-reason" value={reopenReasonCode} autoFocus onChange={(event) => { setReopenReasonCode(event.target.value); setReopenFormError('') }}>
            {reopenReasons.map((reason, index) => <option key={reason.value} value={reason.value}>{copy.reopenReasons[index]}</option>)}
          </select>
          {reopenReasonCode === 'other' && <><label htmlFor="reopen-reason-note">{copy.specify}</label><input id="reopen-reason-note" value={reopenReasonNote} maxLength={500} onChange={(event) => { setReopenReasonNote(event.target.value); setReopenFormError('') }} /></>}
          {reopenFormError && <p className="form-help" role="alert">{reopenFormError}</p>}
          <div className="confirmation-actions"><button className="secondary-button" type="button" onClick={closeReopenDialog} disabled={Boolean(moving)}>{copy.cancel}</button><button className="primary-button" type="submit" disabled={Boolean(moving)}>{moving ? copy.reopening : copy.confirmReopen}</button></div>
        </form>
      </section>
    </div>}
    {lossIntent && <div className="confirmation-overlay" onMouseDown={closeLossDialog}>
      <section className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="loss-prospect-title" onMouseDown={(event) => event.stopPropagation()}>
        <h2 id="loss-prospect-title">{copy.lossTitle}</h2>
        <p>{copy.lossHelp}</p>
        <form className="status-operation-form" onSubmit={confirmLoss}>
          <label htmlFor="loss-reason">{copy.lossReason}</label>
          <select id="loss-reason" value={lossReasonCode} autoFocus onChange={(event) => { setLossReasonCode(event.target.value); setLossFormError('') }}>
            {lossReasons.map((reason, index) => <option key={reason.value} value={reason.value}>{copy.lostReasons[index]}</option>)}
          </select>
          {lossReasonCode === 'other' && <><label htmlFor="loss-reason-note">{copy.specify}</label><input id="loss-reason-note" value={lossReasonNote} maxLength={500} onChange={(event) => { setLossReasonNote(event.target.value); setLossFormError('') }} /></>}
          {lossFormError && <p className="form-help" role="alert">{lossFormError}</p>}
          <div className="confirmation-actions"><button className="secondary-button" type="button" onClick={closeLossDialog} disabled={Boolean(moving)}>{copy.cancel}</button><button className="danger-button" type="submit" disabled={Boolean(moving)}>{moving ? copy.confirmingLoss : copy.confirmLoss}</button></div>
        </form>
      </section>
    </div>}
  </main>
}
