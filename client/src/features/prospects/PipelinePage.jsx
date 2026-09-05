import { useCallback, useEffect, useRef, useState } from 'react'

import { Building2, LoaderCircle, Search } from '../../icons'
import { followInternalLink } from '../../app/navigation'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { createRequestId } from '../../shared/ids/requestId'
import { prospectApi } from './api/prospectApi'


function stageLabel(stage) {
  return stage.labels?.['fr-CA'] ?? stage.labels?.['en-CA'] ?? stage.code
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
  const requestRef = useRef(null)
  const canMove = session.capabilities.includes('pipeline:move')
  const canReopen = session.capabilities.includes('pipeline:reopen')

  const load = useCallback(async () => {
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setLoading(true)
    setError('')
    try {
      setBoard(await prospectApi.pipelineBoard({ searchText: submittedSearch }, controller.signal))
    } catch (requestError) {
      if (requestError?.name !== 'AbortError') setError(toUserMessage(requestError, 'Impossible de charger le pipeline.'))
    } finally {
      if (requestRef.current === controller) requestRef.current = null
      setLoading(false)
    }
  }, [submittedSearch])

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
      setError(toUserMessage(requestError, 'Impossible de déplacer le prospect.'))
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
      setError(toUserMessage(requestError, 'Impossible de charger davantage de prospects.'))
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
      setLossFormError('Précisez le motif de perte.')
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
      setReopenFormError('Précisez le motif de réouverture.')
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
      setError(toUserMessage(requestError, 'Impossible de réouvrir le prospect.'))
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
      <div><p className="eyebrow">Portefeuille CRM</p><h1 id="pipeline-title">Pipeline commercial</h1><p>Suivez les prospects par étape. Chaque déplacement est contrôlé et inscrit au journal d’activité.</p></div>
    </header>
    <form onSubmit={submit} className="prospect-search-form pipeline-search"><label className="sr-only" htmlFor="pipeline-search">Filtrer le pipeline</label><Search size={18} /><input id="pipeline-search" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Filtrer un nom, un secteur ou une ville" /><button className="secondary-button" type="submit">Filtrer</button></form>
    {error && <ErrorBanner><span>{error}</span><button className="link-button" type="button" onClick={load}>Réessayer</button></ErrorBanner>}
    {loading ? <div className="administration-loading" role="status"><LoaderCircle className="spin" size={20} /> Chargement du pipeline…</div> : <section className="pipeline-board" aria-label="Pipeline commercial">
      {board.stages.map((stage, index) => <section className={`pipeline-column pipeline-${stage.color_token}`} key={stage.code} aria-labelledby={`stage-${stage.code}`}>
        <header><h2 id={`stage-${stage.code}`}>{stageLabel(stage)}</h2><span>{(board.columns?.[stage.code] ?? []).length}</span></header>
        <div className="pipeline-cards">{(board.columns?.[stage.code] ?? []).map((prospect) => <article className="pipeline-card" key={prospect.id}>
          <a href={`/app/prospects/${encodeURIComponent(prospect.id)}`} onClick={(event) => followInternalLink(event, `/app/prospects/${encodeURIComponent(prospect.id)}`)}><Building2 size={16} /><strong>{prospect.internal_alias}</strong></a>
          <small>Priorité {prospect.priority}/5</small>
          {canMove && stage.code !== 'lost' && stage.code !== 'won' && <div className="pipeline-move-actions">
            {index > 0 && <button type="button" disabled={moving === prospect.id} onClick={() => move(prospect, board.stages[index - 1])}>← {stageLabel(board.stages[index - 1])}</button>}
            {index < board.stages.length - 1 && <button type="button" disabled={moving === prospect.id} onClick={() => move(prospect, board.stages[index + 1])}>{stageLabel(board.stages[index + 1])} →</button>}
            <button type="button" disabled={moving === prospect.id} onClick={() => move(prospect, board.stages.find((candidate) => candidate.code === 'lost'))}>Marquer perdu</button>
          </div>}
          {canReopen && (stage.code === 'lost' || stage.code === 'won') && <div className="pipeline-move-actions"><button type="button" disabled={moving === prospect.id} onClick={() => requestReopen(prospect)}>Réouvrir</button></div>}
        </article>)}</div>
        {board.next_cursors?.[stage.code] && (board.columns?.[stage.code] ?? []).length < 50 && <button className="secondary-button pipeline-load-more" type="button" disabled={loadingColumns[stage.code]} onClick={() => loadMore(stage.code)}>{loadingColumns[stage.code] ? 'Chargement…' : 'Charger plus'}</button>}
      </section>)}
    </section>}
    {reopenIntent && <div className="confirmation-overlay" onMouseDown={closeReopenDialog}>
      <section className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="reopen-prospect-title" onMouseDown={(event) => event.stopPropagation()}>
        <h2 id="reopen-prospect-title">Réouvrir le prospect</h2>
        <p>Choisissez le motif commercial qui explique la reprise du suivi.</p>
        <form className="status-operation-form" onSubmit={reopen}>
          <label htmlFor="reopen-reason">Motif de réouverture</label>
          <select id="reopen-reason" value={reopenReasonCode} autoFocus onChange={(event) => { setReopenReasonCode(event.target.value); setReopenFormError('') }}>
            {reopenReasons.map((reason) => <option key={reason.value} value={reason.value}>{reason.label}</option>)}
          </select>
          {reopenReasonCode === 'other' && <><label htmlFor="reopen-reason-note">Précisez le motif</label><input id="reopen-reason-note" value={reopenReasonNote} maxLength={500} onChange={(event) => { setReopenReasonNote(event.target.value); setReopenFormError('') }} /></>}
          {reopenFormError && <p className="form-help" role="alert">{reopenFormError}</p>}
          <div className="confirmation-actions"><button className="secondary-button" type="button" onClick={closeReopenDialog} disabled={Boolean(moving)}>Annuler</button><button className="primary-button" type="submit" disabled={Boolean(moving)}>{moving ? 'Réouverture…' : 'Confirmer la réouverture'}</button></div>
        </form>
      </section>
    </div>}
    {lossIntent && <div className="confirmation-overlay" onMouseDown={closeLossDialog}>
      <section className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="loss-prospect-title" onMouseDown={(event) => event.stopPropagation()}>
        <h2 id="loss-prospect-title">Marquer le prospect comme perdu</h2>
        <p>Choisissez le motif commercial qui explique l’arrêt du suivi.</p>
        <form className="status-operation-form" onSubmit={confirmLoss}>
          <label htmlFor="loss-reason">Motif de perte</label>
          <select id="loss-reason" value={lossReasonCode} autoFocus onChange={(event) => { setLossReasonCode(event.target.value); setLossFormError('') }}>
            {lossReasons.map((reason) => <option key={reason.value} value={reason.value}>{reason.label}</option>)}
          </select>
          {lossReasonCode === 'other' && <><label htmlFor="loss-reason-note">Précisez le motif</label><input id="loss-reason-note" value={lossReasonNote} maxLength={500} onChange={(event) => { setLossReasonNote(event.target.value); setLossFormError('') }} /></>}
          {lossFormError && <p className="form-help" role="alert">{lossFormError}</p>}
          <div className="confirmation-actions"><button className="secondary-button" type="button" onClick={closeLossDialog} disabled={Boolean(moving)}>Annuler</button><button className="danger-button" type="submit" disabled={Boolean(moving)}>{moving ? 'Mise à jour…' : 'Confirmer la perte'}</button></div>
        </form>
      </section>
    </div>}
  </main>
}
