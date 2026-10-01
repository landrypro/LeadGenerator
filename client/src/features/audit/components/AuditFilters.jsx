import { useEffect, useState } from 'react'

import { createCustomPeriodFilters, createPeriodFilters } from '../hooks/useAuditEvents'
import { entityTypes } from '../catalog'


export function AuditFilters({ actions, actors = [], filters, loadingActors = false, locale = 'fr-CA', moreActors = false, onApply, onLoadMoreActors, onReset }) {
  const copy = locale === 'en-CA' ? { periodTooLong: 'The period can cover at most 90 days.', entityTypeRequired: 'Choose the entity type.', invalid: 'The filters are invalid.', filters: 'Activity log filters', period: 'Period', days: 'days', custom: 'Custom', from: 'From', to: 'To', action: 'Action', allActions: 'All actions', entityType: 'Entity type', allTypes: 'All types', entityId: 'Entity ID', uuid: 'Exact UUID (optional)', actor: 'Actor', allActors: 'All actors', loadingActors: 'Loading actors…', moreActors: 'Load more actors', reset: 'Reset', apply: 'Apply' } : { periodTooLong: 'La période doit couvrir au plus 90 jours.', entityTypeRequired: 'Choisissez le type de l’entité.', invalid: 'Les filtres sont invalides.', filters: 'Filtres du journal', period: 'Période', days: 'jours', custom: 'Personnalisée', from: 'Du', to: 'Au', action: 'Action', allActions: 'Toutes les actions', entityType: 'Type d’entité', allTypes: 'Tous les types', entityId: 'Identifiant d’entité', uuid: 'UUID exact (facultatif)', actor: 'Acteur', allActors: 'Tous les acteurs', loadingActors: 'Chargement des acteurs…', moreActors: 'Charger plus d’acteurs', reset: 'Réinitialiser', apply: 'Appliquer' }
  const [draft, setDraft] = useState(() => toDraft(filters))
  const [period, setPeriod] = useState('30')
  const [error, setError] = useState('')

  useEffect(() => setDraft(toDraft(filters)), [filters])

  function change(field, value) {
    setDraft((current) => ({ ...current, [field]: value }))
    setError('')
  }

  function selectPeriod(value) {
    setPeriod(value)
    setError('')
  }

  function submit(event) {
    event.preventDefault()
    const selections = {
      action: draft.action,
      entityType: draft.entityType,
      entityId: draft.entityId.trim(),
      actorId: draft.actorId,
    }
    try {
      const nextFilters = period === 'custom'
        ? createCustomPeriodFilters(draft.fromDate, draft.toDate, selections)
        : createPeriodFilters(Number(period), selections)
      const duration = new Date(nextFilters.occurredTo) - new Date(nextFilters.occurredFrom)
      if (duration <= 0 || duration > 90 * 24 * 60 * 60 * 1000) throw new Error(copy.periodTooLong)
      if (nextFilters.entityId && !nextFilters.entityType) throw new Error(copy.entityTypeRequired)
      onApply(nextFilters)
    } catch (submitError) {
      setError(submitError.message || copy.invalid)
    }
  }

  function reset() {
    setPeriod('30')
    setError('')
    onReset()
  }

  return <form className="audit-filters administration-card" aria-label={copy.filters} onSubmit={submit}>
    <fieldset className="audit-periods">
      <legend>{copy.period}</legend>
      <div className="audit-period-options">
        {['7', '30', '90'].map((days) => <label key={days}>
          <input type="radio" name="audit-period" value={days} checked={period === days} onChange={() => selectPeriod(days)} />
          <span>{days} {copy.days}</span>
        </label>)}
        <label>
          <input type="radio" name="audit-period" value="custom" checked={period === 'custom'} onChange={() => selectPeriod('custom')} />
          <span>{copy.custom}</span>
        </label>
      </div>
    </fieldset>

    {period === 'custom' && <div className="audit-custom-period">
      <label htmlFor="audit-date-from">{copy.from}</label>
      <input id="audit-date-from" type="date" value={draft.fromDate} onChange={(event) => change('fromDate', event.target.value)} required />
      <label htmlFor="audit-date-to">{copy.to}</label>
      <input id="audit-date-to" type="date" value={draft.toDate} onChange={(event) => change('toDate', event.target.value)} required />
    </div>}

    <div className="audit-filter-grid">
      <label>{copy.action}
        <select value={draft.action} onChange={(event) => change('action', event.target.value)}>
          <option value="">{copy.allActions}</option>
          {actions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
      </label>
      <label>{copy.entityType}
        <select value={draft.entityType} onChange={(event) => change('entityType', event.target.value)}>
          <option value="">{copy.allTypes}</option>
          {entityTypes(locale).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
      </label>
      <label>{copy.entityId}
        <input value={draft.entityId} onChange={(event) => change('entityId', event.target.value)} placeholder={copy.uuid} maxLength="36" />
      </label>
      <label>{copy.actor}
        <select value={draft.actorId} onChange={(event) => change('actorId', event.target.value)}>
          <option value="">{copy.allActors}</option>
          {actors.map((actor) => <option value={actor.id} key={actor.id}>{actor.displayName}</option>)}
        </select>
      </label>
    </div>

    {moreActors && <button className="text-button audit-more-actors" type="button" onClick={onLoadMoreActors} disabled={loadingActors}>
      {loadingActors ? copy.loadingActors : copy.moreActors}
    </button>}
    {error && <p className="audit-filter-error" role="alert">{error}</p>}
    <div className="audit-filter-actions">
      <button className="secondary-button" type="button" onClick={reset}>{copy.reset}</button>
      <button className="primary-button" type="submit">{copy.apply}</button>
    </div>
  </form>
}


function toDraft(filters) {
  return {
    fromDate: filters.occurredFrom.slice(0, 10),
    toDate: filters.occurredTo.slice(0, 10),
    action: filters.action,
    entityType: filters.entityType,
    entityId: filters.entityId,
    actorId: filters.actorId,
  }
}
