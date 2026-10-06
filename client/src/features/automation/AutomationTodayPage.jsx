import { useState } from 'react'

import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { automationApi } from './api/automationApi'
import { AutomationWorkspace } from './AutomationWorkspace'


const COPY = {
  'fr-CA': {
    title: 'Automatisation — Aujourd’hui', intro: 'Décrivez ce que vous souhaitez examiner. L’assistant prépare uniquement un plan en lecture seule.',
    label: 'Votre demande', placeholder: 'Ex. : montre-moi les prospects ouverts qui me sont attribués', submit: 'Préparer un plan', loading: 'Préparation…',
    suggestions: 'Suggestions guidées', scope_open_prospects: 'Cadrer mes prospects ouverts', rebalance_open_prospects: 'Étudier un rééquilibrage', prepare_new_prospect_followup: 'Préparer le suivi des nouveaux prospects',
    ready: 'Plan proposé', clarification_required: 'Précisez votre demande', intent_not_supported: 'Cette demande n’est pas prise en charge dans IMP-A5.', fallback_guided: 'Le mode libre est temporairement indisponible. Utilisez une suggestion guidée.',
    resolved: 'Éléments trouvés', bounded: 'Éléments retenus', controls: 'Garde-fous appliqués', noEffects: 'Ce qui n’a pas été fait', prepare: 'Préparer ce plan', prepared: 'Plan marqué comme prêt dans cet écran. Aucune donnée ni tâche n’a été créée.',
    counter: 'caractères sur 500', error: 'Impossible de préparer le plan.',
  },
  'en-CA': {
    title: 'Automation — Today', intro: 'Describe what you want to review. The assistant only prepares a read-only plan.',
    label: 'Your request', placeholder: 'E.g. show my assigned open prospects', submit: 'Prepare a plan', loading: 'Preparing…', suggestions: 'Guided suggestions',
    scope_open_prospects: 'Scope my open prospects', rebalance_open_prospects: 'Review a rebalance', prepare_new_prospect_followup: 'Prepare new prospect follow-up',
    ready: 'Proposed plan', clarification_required: 'Clarify your request', intent_not_supported: 'This request is not supported in IMP-A5.', fallback_guided: 'Free text is temporarily unavailable. Use a guided suggestion.',
    resolved: 'Items found', bounded: 'Items included', controls: 'Applied safeguards', noEffects: 'What was not done', prepare: 'Prepare this plan', prepared: 'Plan marked ready on this screen. No data or task was created.',
    counter: 'characters out of 500', error: 'Could not prepare the plan.',
  },
}

const GUIDED = ['scope_open_prospects', 'rebalance_open_prospects', 'prepare_new_prospect_followup']

export function AutomationTodayPage({ session }) {
  const locale = session.active_organization?.locale ?? 'fr-CA'
  const copy = COPY[locale] ?? COPY['fr-CA']
  const [text, setText] = useState('')
  const [outcome, setOutcome] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [prepared, setPrepared] = useState(false)

  const requestPlan = async (payload) => {
    setLoading(true); setError(''); setPrepared(false)
    try { setOutcome(await automationApi.createPlan(payload)) }
    catch (cause) { setError(toUserMessage(cause, copy.error)) }
    finally { setLoading(false) }
  }
  const submit = (event) => { event.preventDefault(); if (text.trim()) requestPlan({ input_mode: 'free_text', user_text: text.trim(), suggestion_code: null }) }
  const suggestions = outcome?.suggestion_codes?.length ? outcome.suggestion_codes : GUIDED

  return <AutomationWorkspace activeSection="today" locale={locale}>
    <header className="automation-page-heading"><p className="eyebrow">IMP-A5</p><h1>{copy.title}</h1><p>{copy.intro}</p></header>
    {error && <ErrorBanner>{error}</ErrorBanner>}
    <form className="surface-card automation-command" onSubmit={submit}>
      <label htmlFor="assistant-request">{copy.label}</label>
      <textarea id="assistant-request" maxLength={500} rows={5} value={text} placeholder={copy.placeholder} onChange={event => setText(event.target.value)} />
      <div className="automation-command__footer"><span aria-live="polite">{text.length} {copy.counter}</span><button className="primary-button" disabled={loading || !text.trim()}>{loading ? copy.loading : copy.submit}</button></div>
    </form>
    <section className="surface-card" aria-labelledby="assistant-suggestions"><h2 id="assistant-suggestions">{copy.suggestions}</h2><div className="button-row">
      {suggestions.map(code => <button type="button" className="secondary-button" disabled={loading} key={code} onClick={() => requestPlan({ input_mode: 'guided', user_text: null, suggestion_code: code })}>{copy[code] ?? code}</button>)}
    </div></section>
    {outcome && <section className="surface-card" aria-live="polite">
      <h2>{outcome.result_code === 'plan_ready' ? copy.ready : copy[outcome.result_code]}</h2>
      {outcome.plan && <><dl className="automation-plan"><div><dt>{copy.resolved}</dt><dd>{outcome.plan.resolved_count ?? '—'}</dd></div><div><dt>{copy.bounded}</dt><dd>{outcome.plan.bounded_count ?? '—'}</dd></div></dl>
        <h3>{copy.controls}</h3><ul>{outcome.plan.control_codes.map(code => <li key={code}>{code.replaceAll('_', ' ')}</li>)}</ul>
        <h3>{copy.noEffects}</h3><ul>{outcome.plan.not_performed_codes.map(code => <li key={code}>{code.replaceAll('_', ' ')}</li>)}</ul>
        <button type="button" className="primary-button" onClick={() => setPrepared(true)}>{copy.prepare}</button>{prepared && <p role="status">{copy.prepared}</p>}</>}
    </section>}
  </AutomationWorkspace>
}
