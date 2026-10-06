import { useEffect, useState } from 'react'

import { ErrorBanner } from '../../shared/ui/Feedback'
import { AutomationWorkspace } from './AutomationWorkspace'
import { automationApi } from './api/automationApi'


const COPY = {
  'fr-CA': {
    eyebrow: 'AUTOMATISATION', title: 'Entrées et exceptions', intro: 'Les cas qui nécessitent une vérification ou une décision humaine seront regroupés ici.',
    emptyTitle: 'Aucune entrée ou exception à traiter',
    emptyText: 'Aucune entrée ou exception n’est actuellement disponible pour l’organisation active. Les cas nécessitant une vérification apparaîtront ici ; aucun traitement automatique n’est en attente.',
    statesTitle: 'États qui seront suivis', states: ['Ouverte', 'En traitement', 'À vérifier', 'Résolue', 'Abandonnée'],
    notice: 'Cet état est une absence de donnée confirmée. Un problème de chargement sera affiché comme une erreur récupérable, et non comme un état vide.',
    loading: 'Chargement des entrées et exceptions…', error: 'Impossible de charger les entrées et exceptions. Réessayez plus tard.',
    currentTitle: 'Entrées et exceptions à traiter', stateLabels: { open: 'Ouverte', in_progress: 'En traitement', resolved: 'Résolue', abandoned: 'Abandonnée' },
    claim: 'Prendre en charge', resolve: 'Résoudre', abandon: 'Abandonner', reconcile: 'Réconcilier sans retry',
    confirm: 'Confirmer', cancel: 'Annuler', confirmText: 'Confirmez cette décision humaine. Aucun effet CRM ni retry automatique ne sera déclenché.',
    actionDone: 'Exception mise à jour sans effet CRM ni retry automatique.',
  },
  'en-CA': {
    eyebrow: 'AUTOMATION', title: 'Entries and exceptions', intro: 'Cases that require verification or a human decision will be grouped here.',
    emptyTitle: 'No entries or exceptions to review',
    emptyText: 'No entry or exception is currently available for the active organization. Cases requiring verification will appear here; no automated treatment is pending.',
    statesTitle: 'States that will be tracked', states: ['Open', 'In progress', 'To verify', 'Resolved', 'Abandoned'],
    notice: 'This is a confirmed absence of data. A loading problem will be displayed as a recoverable error, not as an empty state.',
    loading: 'Loading entries and exceptions…', error: 'Unable to load entries and exceptions. Try again later.',
    currentTitle: 'Entries and exceptions to review', stateLabels: { open: 'Open', in_progress: 'In progress', resolved: 'Resolved', abandoned: 'Abandoned' },
    claim: 'Claim', resolve: 'Resolve', abandon: 'Abandon', reconcile: 'Reconcile without retry',
    confirm: 'Confirm', cancel: 'Cancel', confirmText: 'Confirm this human decision. No CRM effect or automatic retry will be triggered.',
    actionDone: 'Exception updated without a CRM effect or automatic retry.',
  },
}


export function AutomationExceptionsPage({ session }) {
  const locale = session.active_organization?.locale ?? 'fr-CA'
  const copy = COPY[locale] ?? COPY['fr-CA']
  const [page, setPage] = useState({ items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [pendingCommand, setPendingCommand] = useState(null)
  const [runningId, setRunningId] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    automationApi.listExceptions(controller.signal)
      .then(result => setPage(result))
      .catch(fetchError => {
        if (fetchError?.name !== 'AbortError') setError(fetchError?.message || copy.error)
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [copy.error, locale])

  const canResolve = session.capabilities?.includes('automation:exceptions:resolve:self') ?? false

  async function confirmCommand() {
    if (!pendingCommand) return
    const { id, command, version } = pendingCommand
    setRunningId(id)
    setError('')
    setNotice('')
    try {
      const resolutionCode = command === 'resolve'
        ? 'human_review_complete'
        : command === 'abandon'
          ? 'not_actionable'
          : undefined
      const idempotencyKey = globalThis.crypto?.randomUUID?.() || `${command}-${id}-${Date.now()}`
      const result = await automationApi.transitionException(id, command, version, idempotencyKey, { resolutionCode })
      setPage(current => ({
        ...current,
        items: (current.items || []).map(item => item.id === id ? { ...item, ...result.item } : item),
      }))
      setNotice(copy.actionDone)
      setPendingCommand(null)
    } catch (requestError) {
      setError(requestError?.message || copy.error)
    } finally {
      setRunningId('')
    }
  }

  function commandsFor(item) {
    if (!canResolve) return []
    if (item.state === 'open') return ['claim']
    if (item.state === 'in_progress') return ['resolve', 'abandon', 'reconcile']
    return []
  }

  return <AutomationWorkspace activeSection="exceptions" locale={locale}>
    <header className="automation-page-heading">
      <p className="eyebrow">{copy.eyebrow}</p>
      <h1>{copy.title}</h1>
      <p>{copy.intro}</p>
    </header>
    {loading && <p role="status" className="form-help">{copy.loading}</p>}
    {error && <ErrorBanner>{error}</ErrorBanner>}
    {notice && <p className="success-banner" role="status">{notice}</p>}
    {!loading && !error && page.items?.length > 0 && <section className="surface-card automation-empty-state" aria-labelledby="automation-exceptions-current-title">
      <h2 id="automation-exceptions-current-title">{copy.currentTitle}</h2>
      <ul className="automation-state-list">
        {page.items.map(item => <li key={item.id} className="automation-exception-item">
          <strong>{item.exception_code}</strong> · {copy.stateLabels[item.state] || item.state}
          {pendingCommand?.id !== item.id && commandsFor(item).map(command => <button
            key={command}
            type="button"
            className="secondary-button"
            disabled={runningId === item.id}
            onClick={() => setPendingCommand({ id: item.id, command, version: item.version })}
          >{copy[command]}</button>)}
          {pendingCommand?.id === item.id && <span className="automation-transition-confirmation" role="group" aria-label={copy.confirmText}>
            <span className="form-help">{copy.confirmText}</span>
            <button type="button" className="secondary-button" disabled={runningId === item.id} onClick={() => setPendingCommand(null)}>{copy.cancel}</button>
            <button type="button" className="primary-button" disabled={runningId === item.id} onClick={confirmCommand}>{copy.confirm}</button>
          </span>}
        </li>)}
      </ul>
      <p className="form-help">{copy.notice}</p>
    </section>}
    {!loading && !error && page.items?.length === 0 && <section className="surface-card automation-empty-state" aria-labelledby="automation-exceptions-empty-title">
      <h2 id="automation-exceptions-empty-title">{copy.emptyTitle}</h2>
      <p>{copy.emptyText}</p>
      <h3>{copy.statesTitle}</h3>
      <ul className="automation-state-list">{copy.states.map(state => <li key={state}>{state}</li>)}</ul>
      <p className="form-help">{copy.notice}</p>
    </section>}
  </AutomationWorkspace>
}
