import { useEffect, useState } from 'react'

import { ErrorBanner } from '../../shared/ui/Feedback'
import { AutomationWorkspace } from './AutomationWorkspace'
import { automationApi } from './api/automationApi'


const COPY = {
  'fr-CA': {
    eyebrow: 'AUTOMATISATION', title: 'Playbooks', intro: 'Les recettes guidées prépareront des revues explicables. Elles ne créent ni tâche, ni contact, ni changement de pipeline à ce stade.',
    status: 'Prévol et activation non disponibles', availability: 'Cette organisation ne possède pas encore de configuration active.',
    loading: 'Chargement de la configuration disponible…', error: 'Impossible de charger la configuration des Playbooks. Réessayez plus tard.',
    configured: 'Configuration enregistrée', preflight: 'Dernier Prévol :', states: { draft: 'Brouillon', preflight_required: 'Prévol requis', ready: 'Prêt à vérifier', active_prepare: 'Actif — préparer', suspended: 'Suspendu', retired: 'Retiré' },
    runPreflight: 'Lancer un Prévol', runningPreflight: 'Prévol en cours…', preflightDone: 'Prévol enregistré sans effet CRM ni envoi externe.',
    activate: 'Activer en mode préparer', suspend: 'Suspendre', resume: 'Reprendre : nouveau Prévol requis',
    confirm: 'Confirmer', cancel: 'Annuler', confirmTransition: 'Confirmez cette transition. Elle ne crée aucun effet CRM ni envoi externe.',
    lifecycleDone: 'État du Playbook mis à jour. Aucun effet CRM ni envoi externe n’a été créé.',
    cards: [
      ['Nouveau prospect', 'Préparer une revue d’un nouveau prospect en respectant les données CRM et les permissions.'],
      ['Proposition en attente', 'Repérer une opportunité à l’étape proposition qui mérite une revue humaine.'],
      ['Occasion oubliée', 'Repérer une opportunité ouverte sans activité ou prochaine action suffisante.'],
    ],
    boundary: 'Ce qui n’est pas fait', boundaryText: 'Aucun envoi externe, aucune réattribution, aucune fusion et aucun mouvement du pipeline ne sont lancés depuis cet écran.',
  },
  'en-CA': {
    eyebrow: 'AUTOMATION', title: 'Playbooks', intro: 'Guided recipes will prepare explainable reviews. They do not create a task, contact, or pipeline change at this stage.',
    status: 'Preflight and activation are unavailable', availability: 'This organization does not yet have an active configuration.',
    loading: 'Loading available configuration…', error: 'Unable to load Playbook configuration. Try again later.',
    configured: 'Configuration recorded', preflight: 'Latest Preflight:', states: { draft: 'Draft', preflight_required: 'Preflight required', ready: 'Ready to review', active_prepare: 'Active — prepare', suspended: 'Suspended', retired: 'Retired' },
    runPreflight: 'Run Preflight', runningPreflight: 'Preflight running…', preflightDone: 'Preflight recorded without a CRM effect or external send.',
    activate: 'Activate in prepare mode', suspend: 'Suspend', resume: 'Resume: new Preflight required',
    confirm: 'Confirm', cancel: 'Cancel', confirmTransition: 'Confirm this transition. It creates no CRM effect or external send.',
    lifecycleDone: 'Playbook state updated. No CRM effect or external send was created.',
    cards: [
      ['New prospect', 'Prepare a review of a new prospect while respecting CRM data and permissions.'],
      ['Pending proposal', 'Identify an opportunity at the proposal stage that needs human review.'],
      ['Forgotten opportunity', 'Identify an open opportunity without sufficient activity or next action.'],
    ],
    boundary: 'What is not done', boundaryText: 'No external message, reassignment, merge, or pipeline movement starts from this screen.',
  },
}


export function AutomationPlaybooksPage({ session }) {
  const locale = session.active_organization?.locale ?? 'fr-CA'
  const copy = COPY[locale] ?? COPY['fr-CA']
  const [page, setPage] = useState({ items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [runningCode, setRunningCode] = useState('')
  const [notice, setNotice] = useState('')
  const [pendingTransition, setPendingTransition] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    automationApi.listPlaybooks(controller.signal)
      .then(result => setPage(result))
      .catch(fetchError => {
        if (fetchError?.name !== 'AbortError') setError(fetchError?.message || copy.error)
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [copy.error, locale])

  const configuredByCode = new Map((page.items || []).map(item => [item.code, item]))
  const canRunPreflight = page.preflight_enabled === true
    && (session.capabilities?.includes('automation:preflights:run') ?? false)
  const canActivate = page.lifecycle_enabled === true
    && (session.capabilities?.includes('automation:playbooks:activate') ?? false)
  const canSuspend = page.lifecycle_enabled === true
    && (session.capabilities?.includes('automation:playbooks:suspend') ?? false)

  async function runPreflight(code) {
    setRunningCode(code)
    setError('')
    setNotice('')
    try {
      const idempotencyKey = globalThis.crypto?.randomUUID?.() || `preflight-${code}-${Date.now()}`
      const result = await automationApi.runPreflight(code, idempotencyKey)
      setPage(current => ({
        ...current,
        items: (current.items || []).map(item => item.code === code
          ? { ...item, latest_preflight_state: result.item.state, latest_preflight_expires_at: result.item.expires_at }
          : item),
      }))
      setNotice(copy.preflightDone)
    } catch (requestError) {
      setError(requestError?.message || copy.error)
    } finally {
      setRunningCode('')
    }
  }

  async function confirmTransition() {
    if (!pendingTransition) return
    const { code, command, version } = pendingTransition
    setRunningCode(code)
    setError('')
    setNotice('')
    try {
      const idempotencyKey = globalThis.crypto?.randomUUID?.() || `${command}-${code}-${Date.now()}`
      const result = await automationApi.transitionPlaybook(code, command, version, idempotencyKey, {
        reasonCode: command === 'suspend' ? 'operator_request' : undefined,
      })
      setPage(current => ({
        ...current,
        items: (current.items || []).map(item => item.code === code ? { ...item, ...result.item } : item),
      }))
      setNotice(copy.lifecycleDone)
      setPendingTransition(null)
    } catch (requestError) {
      setError(requestError?.message || copy.error)
    } finally {
      setRunningCode('')
    }
  }

  return <AutomationWorkspace activeSection="playbooks" locale={locale}>
    <header className="automation-page-heading">
      <p className="eyebrow">{copy.eyebrow}</p>
      <h1>{copy.title}</h1>
      <p>{copy.intro}</p>
    </header>
    {loading && <p role="status" className="form-help">{copy.loading}</p>}
    {error && <ErrorBanner>{error}</ErrorBanner>}
    {notice && <p className="success-banner" role="status">{notice}</p>}
    <section className="automation-playbook-grid" aria-label={copy.title}>
      {copy.cards.map(([title, description], index) => {
        const item = configuredByCode.get(['new_prospect', 'proposal_pending', 'forgotten_opportunity'][index])
        const state = item ? (copy.states[item.state] || item.state) : copy.status
        const availability = item
          ? `${copy.configured} · ${state}${item.latest_preflight_state ? ` · ${copy.preflight} ${item.latest_preflight_state}` : ''}`
          : copy.availability
        const command = item?.state === 'ready' && canActivate
          ? 'activate'
          : item?.state === 'active_prepare' && canSuspend
            ? 'suspend'
            : item?.state === 'suspended' && canActivate
              ? 'resume'
              : null
        return <article className="surface-card automation-playbook-card" key={title}>
        <h2>{title}</h2>
        <p>{description}</p>
        <p className="automation-unavailable-status">{state}</p>
        <p className="form-help">{availability}</p>
        {item && canRunPreflight && <button
          type="button"
          className="secondary-button"
          disabled={runningCode === item.code}
          onClick={() => runPreflight(item.code)}
        >{runningCode === item.code ? copy.runningPreflight : copy.runPreflight}</button>}
        {item && command && pendingTransition?.code !== item.code && <button
          type="button"
          className="secondary-button"
          disabled={runningCode === item.code}
          onClick={() => setPendingTransition({ code: item.code, command, version: item.version })}
        >{copy[command]}</button>}
        {item && pendingTransition?.code === item.code && <div className="automation-transition-confirmation" role="group" aria-label={copy.confirmTransition}>
          <p className="form-help">{copy.confirmTransition}</p>
          <button type="button" className="secondary-button" disabled={runningCode === item.code} onClick={() => setPendingTransition(null)}>{copy.cancel}</button>
          <button type="button" className="primary-button" disabled={runningCode === item.code} onClick={confirmTransition}>{copy.confirm}</button>
        </div>}
      </article>
      })}
    </section>
    <section className="surface-card automation-boundary" aria-labelledby="automation-boundary-title">
      <h2 id="automation-boundary-title">{copy.boundary}</h2>
      <p>{copy.boundaryText}</p>
    </section>
  </AutomationWorkspace>
}
