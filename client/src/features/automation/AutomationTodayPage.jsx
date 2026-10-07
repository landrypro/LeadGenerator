import { useEffect, useMemo, useState } from 'react'

import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { automationApi } from './api/automationApi'
import { AutomationWorkspace } from './AutomationWorkspace'


const COPY = {
  'fr-CA': {
    title: 'Automatisation — Aujourd’hui', intro: 'Décrivez ce que vous souhaitez examiner. L’assistant prépare uniquement un plan en lecture seule.',
    label: 'Votre demande', placeholder: 'Ex. : montre-moi les prospects ouverts qui me sont attribués', submit: 'Préparer un plan', loading: 'Préparation…',
    suggestions: 'Suggestions guidées', scope_open_prospects: 'Cadrer mes prospects ouverts', rebalance_open_prospects: 'Étudier un rééquilibrage', prepare_new_prospect_followup: 'Préparer le suivi des nouveaux prospects',
    ready: 'Plan proposé', clarification_required: 'Précisez votre demande', intent_not_supported: 'Cette demande n’est pas prise en charge dans IMP-A5.', fallback_guided: 'Le mode libre est temporairement indisponible. Utilisez une suggestion guidée.', scopeLabel: 'Périmètre examiné :', scopeAssigned: 'prospects ouverts qui vous sont attribués', scopeOrganization: 'prospects ouverts de l’organisation active', scopeNew: 'nouveaux prospects de votre périmètre', scopeStatus: 'état de l’automatisation',
    planMessage: 'Voici une proposition en lecture seule à partir du périmètre autorisé.', clarificationMessage: 'Essayez une formulation proposée ci-dessous, par exemple « Montre-moi les prospects ouverts ».', unsupportedMessage: 'Aucune action n’a été exécutée. Choisissez une suggestion guidée pour rester dans le périmètre disponible.', fallbackMessage: 'Le mode libre n’a pas pu être interprété. Choisissez une suggestion guidée pour obtenir un plan déterministe.',
    resolved: 'Éléments trouvés', bounded: 'Éléments retenus', controls: 'Garde-fous appliqués', noEffects: 'Ce qui n’a pas été fait', prepare: 'Préparer ce plan', prepared: 'Plan marqué comme prêt dans cet écran. Aucune donnée ni tâche n’a été créée.',
    planItems: 'Éléments CRM du plan', noResultsTitle: 'Aucun élément CRM trouvé', noResultsMessage: 'Le périmètre autorisé ne contient aucun élément correspondant à cette demande.', itemsUnavailableTitle: 'Éléments non affichés', itemsUnavailableMessage: 'Le plan contient des éléments, mais aucun détail n’est disponible dans cette vue bornée.', retry: 'Réessayer',
    assistantUnavailableTitle: 'Préparation de plans indisponible', assistantUnavailableMessage: 'L’assistant n’est pas activé pour cette organisation ou cet environnement. Les données CRM restent consultables, sans préparation de plan.',
    counter: 'caractères sur 500', error: 'Impossible de préparer le plan.',
    crmTitle: 'Données CRM en direct', crmOpenProspects: 'Prospects ouverts', crmDueTasks: 'Tâches à échéance', crmOverdueTasks: 'Tâches en retard', crmOpenOpportunities: 'Opportunités ouvertes',
    crmItemsTitle: 'Priorités issues du CRM', crmEmpty: 'Aucune priorité CRM ne nécessite une revue immédiate.', crmLoading: 'Chargement des données CRM…', crmError: 'Impossible de charger les données CRM du jour.',
    itemTypes: { task: 'Tâche', prospect: 'Prospect', opportunity: 'Opportunité' },
  },
  'en-CA': {
    title: 'Automation — Today', intro: 'Describe what you want to review. The assistant only prepares a read-only plan.',
    label: 'Your request', placeholder: 'E.g. show my assigned open prospects', submit: 'Prepare a plan', loading: 'Preparing…', suggestions: 'Guided suggestions',
    scope_open_prospects: 'Scope my open prospects', rebalance_open_prospects: 'Review a rebalance', prepare_new_prospect_followup: 'Prepare new prospect follow-up',
    ready: 'Proposed plan', clarification_required: 'Clarify your request', intent_not_supported: 'This request is not supported in IMP-A5.', fallback_guided: 'Free text is temporarily unavailable. Use a guided suggestion.', scopeLabel: 'Scope reviewed:', scopeAssigned: 'your assigned open prospects', scopeOrganization: 'open prospects in the active organization', scopeNew: 'new prospects in your scope', scopeStatus: 'automation status',
    planMessage: 'Here is a read-only proposal based on the authorized scope.', clarificationMessage: 'Try one of the suggestions below, for example “Show me my open prospects”.', unsupportedMessage: 'No action was executed. Choose a guided suggestion to stay within the available scope.', fallbackMessage: 'Free text could not be interpreted. Choose a guided suggestion to get a deterministic plan.',
    resolved: 'Items found', bounded: 'Items included', controls: 'Applied safeguards', noEffects: 'What was not done', prepare: 'Prepare this plan', prepared: 'Plan marked ready on this screen. No data or task was created.',
    planItems: 'CRM items in this plan', noResultsTitle: 'No CRM items found', noResultsMessage: 'The authorized scope contains no item matching this request.', itemsUnavailableTitle: 'Items not displayed', itemsUnavailableMessage: 'The plan contains items, but no detail is available in this bounded view.', retry: 'Try again',
    assistantUnavailableTitle: 'Plan preparation unavailable', assistantUnavailableMessage: 'The assistant is not enabled for this organization or environment. CRM data remains available without plan preparation.',
    counter: 'characters out of 500', error: 'Could not prepare the plan.',
    crmTitle: 'Live CRM data', crmOpenProspects: 'Open prospects', crmDueTasks: 'Due tasks', crmOverdueTasks: 'Overdue tasks', crmOpenOpportunities: 'Open opportunities',
    crmItemsTitle: 'CRM priorities', crmEmpty: 'No CRM priority requires immediate review.', crmLoading: 'Loading CRM data…', crmError: 'Could not load today’s CRM data.',
    itemTypes: { task: 'Task', prospect: 'Prospect', opportunity: 'Opportunity' },
  },
}

const GUIDED = ['scope_open_prospects', 'rebalance_open_prospects', 'prepare_new_prospect_followup']

function normalizeSuggestionText(value) {
  return value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/[’']/g, "'")
}

export function AutomationTodayPage({ session }) {
  const locale = session.active_organization?.locale ?? 'fr-CA'
  const copy = COPY[locale] ?? COPY['fr-CA']
  const [text, setText] = useState('')
  const [outcome, setOutcome] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [prepared, setPrepared] = useState(false)
  const [today, setToday] = useState({ counts: {}, items: [] })
  const [todayLoading, setTodayLoading] = useState(true)
  const [todayError, setTodayError] = useState('')
  const [todayRefresh, setTodayRefresh] = useState(0)
  const [catalogSuggestions, setCatalogSuggestions] = useState([])
  const [suggestionsOpen, setSuggestionsOpen] = useState(false)
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(0)
  const [lastRequest, setLastRequest] = useState(null)
  const assistantAvailable = session.automation_assistant_available !== false

  useEffect(() => {
    const controller = new AbortController()
    setTodayLoading(true)
    setTodayError('')
    automationApi.getToday(controller.signal)
      .then(result => setToday(result || { counts: {}, items: [] }))
      .catch(cause => {
        if (cause?.name !== 'AbortError') setTodayError(toUserMessage(cause, copy.crmError))
      })
      .finally(() => { if (!controller.signal.aborted) setTodayLoading(false) })
    return () => controller.abort()
  }, [copy.crmError, locale, todayRefresh])

  useEffect(() => {
    const controller = new AbortController()
    if (!assistantAvailable) {
      setCatalogSuggestions([])
      return () => controller.abort()
    }
    if (typeof automationApi.getSuggestions !== 'function') return () => controller.abort()
    automationApi.getSuggestions(controller.signal)
      .then(result => setCatalogSuggestions(Array.isArray(result?.items) ? result.items : []))
      .catch(cause => { if (cause?.name !== 'AbortError') setCatalogSuggestions([]) })
    return () => controller.abort()
  }, [assistantAvailable, locale])

  const requestPlan = async (payload) => {
    setLastRequest(payload); setLoading(true); setError(''); setOutcome(null); setPrepared(false)
    try { setOutcome(await automationApi.createPlan(payload)) }
    catch (cause) { setError(toUserMessage(cause, copy.error)) }
    finally { setLoading(false) }
  }
  const submit = (event) => { event.preventDefault(); if (text.trim()) requestPlan({ input_mode: 'free_text', user_text: text.trim(), suggestion_code: null }) }
  const suggestions = outcome?.suggestion_codes?.length ? outcome.suggestion_codes : GUIDED
  const matchingSuggestions = useMemo(() => {
    const query = normalizeSuggestionText(text.trim())
    if (query.length < 1) return []
    return catalogSuggestions.filter(item => (
      item && typeof item.label === 'string' && typeof item.prompt === 'string' && typeof item.code === 'string'
      && [item.label, item.prompt, item.code].some(value => normalizeSuggestionText(value).includes(query))
    ))
  }, [catalogSuggestions, text])
  const suggestionListOpen = suggestionsOpen && matchingSuggestions.length > 0
  const selectSuggestion = (suggestion) => {
    setText(suggestion.prompt)
    setActiveSuggestionIndex(0)
    setSuggestionsOpen(false)
  }
  const handleRequestKeyDown = (event) => {
    if (!suggestionListOpen) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveSuggestionIndex(index => (index + 1) % matchingSuggestions.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveSuggestionIndex(index => (index - 1 + matchingSuggestions.length) % matchingSuggestions.length)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      selectSuggestion(matchingSuggestions[activeSuggestionIndex])
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setSuggestionsOpen(false)
    }
  }

  const outcomeTitle = outcome?.result_code === 'plan_ready'
    ? copy.ready
    : copy[outcome?.result_code] ?? copy.intent_not_supported
  const outcomeMessages = {
    plan_ready: copy.planMessage,
    clarification_required: copy.clarificationMessage,
    intent_not_supported: copy.unsupportedMessage,
    fallback_guided: copy.fallbackMessage,
  }
  const outcomeMessage = outcomeMessages[outcome?.result_code] ?? copy.unsupportedMessage
  const scopeLabels = {
    assigned_open_prospects: copy.scopeAssigned,
    organization_open_prospects: copy.scopeOrganization,
    new_prospects: copy.scopeNew,
    automation_status: copy.scopeStatus,
  }
  const outcomeScope = scopeLabels[outcome?.intent?.scope_kind]
  const planHasCrmResolution = typeof outcome?.plan?.resolved_count === 'number'
  const planItems = Array.isArray(outcome?.plan?.items) ? outcome.plan.items : []

  return <AutomationWorkspace activeSection="today" locale={locale}>
    <header className="automation-page-heading"><p className="eyebrow">IMP-A5</p><h1>{copy.title}</h1><p>{copy.intro}</p></header>
    {error && <ErrorBanner><span>{error}</span>{lastRequest && <button type="button" className="link-button" disabled={loading} onClick={() => requestPlan(lastRequest)}>{copy.retry}</button>}</ErrorBanner>}
    {!assistantAvailable && <section className="surface-card automation-empty-state" aria-labelledby="assistant-unavailable-title">
      <h2 id="assistant-unavailable-title">{copy.assistantUnavailableTitle}</h2>
      <p>{copy.assistantUnavailableMessage}</p>
    </section>}
    {assistantAvailable && <><form className="surface-card automation-command" onSubmit={submit}>
      <label htmlFor="assistant-request">{copy.label}</label>
      <div className="automation-command__field">
        <textarea
          id="assistant-request"
          aria-autocomplete="list"
          aria-controls={suggestionListOpen ? 'assistant-suggestions-list' : undefined}
          maxLength={500}
          rows={3}
          value={text}
          placeholder={copy.placeholder}
          onChange={event => { setText(event.target.value); setActiveSuggestionIndex(0); setSuggestionsOpen(true) }}
          onFocus={() => setSuggestionsOpen(true)}
          onBlur={() => window.setTimeout(() => setSuggestionsOpen(false), 0)}
          onKeyDown={handleRequestKeyDown}
        />
        {suggestionListOpen && <ul id="assistant-suggestions-list" role="listbox" className="automation-suggestion-list" aria-label={copy.suggestions}>
          {matchingSuggestions.map((suggestion, index) => <li
            id={`assistant-suggestion-${index}`}
            key={suggestion.code}
            role="option"
            aria-selected={index === activeSuggestionIndex}
            onMouseDown={event => { event.preventDefault(); selectSuggestion(suggestion) }}
          >
            <strong>{suggestion.label}</strong>
            <span>{suggestion.prompt}</span>
          </li>)}
        </ul>}
      </div>
      <div className="automation-command__footer"><span aria-live="polite">{text.length} {copy.counter}</span><button className="primary-button" disabled={loading || !text.trim()}>{loading ? copy.loading : copy.submit}</button></div>
    </form>
    <section className="surface-card automation-suggestions" aria-labelledby="assistant-suggestions"><h2 id="assistant-suggestions">{copy.suggestions}</h2><div className="button-row">
      {suggestions.map(code => <button type="button" className="secondary-button" disabled={loading} key={code} onClick={() => requestPlan({ input_mode: 'guided', user_text: null, suggestion_code: code })}>{copy[code] ?? code}</button>)}
    </div></section>
    </>}
    <section className="surface-card automation-crm-context" aria-labelledby="automation-crm-context-title">
      <h2 id="automation-crm-context-title">{copy.crmTitle}</h2>
      {todayLoading && <p role="status" className="form-help">{copy.crmLoading}</p>}
      {todayError && <ErrorBanner><span>{todayError}</span><button type="button" className="link-button" disabled={todayLoading} onClick={() => setTodayRefresh(value => value + 1)}>{copy.retry}</button></ErrorBanner>}
      {!todayLoading && !todayError && <>
        <dl className="automation-plan">
          <div><dt>{copy.crmOpenProspects}</dt><dd>{today.counts?.open_prospects ?? 0}</dd></div>
          <div><dt>{copy.crmDueTasks}</dt><dd>{today.counts?.due_tasks ?? 0}</dd></div>
          <div><dt>{copy.crmOverdueTasks}</dt><dd>{today.counts?.overdue_tasks ?? 0}</dd></div>
          <div><dt>{copy.crmOpenOpportunities}</dt><dd>{today.counts?.open_opportunities ?? 0}</dd></div>
        </dl>
        <h3>{copy.crmItemsTitle}</h3>
        {today.items?.length > 0
          ? <ul className="automation-state-list">{today.items.map(item => <li key={`${item.kind}-${item.id}`}>
            <strong>{copy.itemTypes[item.kind] || item.kind}</strong> · {item.label}
            {item.prospect_label ? ` · ${item.prospect_label}` : ''}
            {item.stage ? ` · ${item.stage}` : ''}
          </li>)}</ul>
          : <p className="form-help">{copy.crmEmpty}</p>}
      </>}
    </section>
    {outcome && <section className="surface-card" aria-live="polite">
      <h2>{outcomeTitle}</h2>
      <p className="automation-result-message" role="status">{outcomeMessage}</p>
      {outcomeScope && <p className="form-help automation-result-scope"><strong>{copy.scopeLabel}</strong> {outcomeScope}</p>}
      {outcome.plan && <><dl className="automation-plan"><div><dt>{copy.resolved}</dt><dd>{outcome.plan.resolved_count ?? '—'}</dd></div><div><dt>{copy.bounded}</dt><dd>{outcome.plan.bounded_count ?? '—'}</dd></div></dl>
        {planHasCrmResolution && outcome.plan.resolved_count === 0 && <div className="automation-empty-state automation-boundary" role="status"><h3>{copy.noResultsTitle}</h3><p>{copy.noResultsMessage}</p></div>}
        {planHasCrmResolution && outcome.plan.resolved_count > 0 && planItems.length > 0 && <><h3>{copy.planItems}</h3><ul className="automation-plan-items">{planItems.map(item => <li key={`${item.kind}-${item.id}`}><strong>{copy.itemTypes[item.kind] || item.kind}</strong><span>{item.label}{item.stage ? ` · ${item.stage}` : ''}{item.priority !== undefined && item.priority !== null ? ` · ${item.priority}` : ''}</span></li>)}</ul></>}
        {planHasCrmResolution && outcome.plan.resolved_count > 0 && planItems.length === 0 && <div className="automation-empty-state automation-boundary" role="status"><h3>{copy.itemsUnavailableTitle}</h3><p>{copy.itemsUnavailableMessage}</p></div>}
        <h3>{copy.controls}</h3><ul>{(outcome.plan.control_codes ?? []).map(code => <li key={code}>{code.replaceAll('_', ' ')}</li>)}</ul>
        <h3>{copy.noEffects}</h3><ul>{(outcome.plan.not_performed_codes ?? []).map(code => <li key={code}>{code.replaceAll('_', ' ')}</li>)}</ul>
        <button type="button" className="primary-button" onClick={() => setPrepared(true)}>{copy.prepare}</button>{prepared && <p role="status">{copy.prepared}</p>}</>}
    </section>}
  </AutomationWorkspace>
}
