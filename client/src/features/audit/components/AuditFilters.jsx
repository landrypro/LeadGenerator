import { useEffect, useState } from 'react'

import { createCustomPeriodFilters, createPeriodFilters } from '../hooks/useAuditEvents'
import { ENTITY_TYPES } from '../catalog'


export function AuditFilters({ actions, actors = [], filters, loadingActors = false, moreActors = false, onApply, onLoadMoreActors, onReset }) {
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
      if (duration <= 0 || duration > 90 * 24 * 60 * 60 * 1000) throw new Error('La période doit couvrir au plus 90 jours.')
      if (nextFilters.entityId && !nextFilters.entityType) throw new Error('Choisissez le type de l’entité.')
      onApply(nextFilters)
    } catch (submitError) {
      setError(submitError.message || 'Les filtres sont invalides.')
    }
  }

  function reset() {
    setPeriod('30')
    setError('')
    onReset()
  }

  return <form className="audit-filters administration-card" aria-label="Filtres du journal" onSubmit={submit}>
    <fieldset className="audit-periods">
      <legend>Période</legend>
      <div className="audit-period-options">
        {['7', '30', '90'].map((days) => <label key={days}>
          <input type="radio" name="audit-period" value={days} checked={period === days} onChange={() => selectPeriod(days)} />
          <span>{days} jours</span>
        </label>)}
        <label>
          <input type="radio" name="audit-period" value="custom" checked={period === 'custom'} onChange={() => selectPeriod('custom')} />
          <span>Personnalisée</span>
        </label>
      </div>
    </fieldset>

    {period === 'custom' && <div className="audit-custom-period">
      <label htmlFor="audit-date-from">Du</label>
      <input id="audit-date-from" type="date" value={draft.fromDate} onChange={(event) => change('fromDate', event.target.value)} required />
      <label htmlFor="audit-date-to">Au</label>
      <input id="audit-date-to" type="date" value={draft.toDate} onChange={(event) => change('toDate', event.target.value)} required />
    </div>}

    <div className="audit-filter-grid">
      <label>Action
        <select value={draft.action} onChange={(event) => change('action', event.target.value)}>
          <option value="">Toutes les actions</option>
          {actions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
      </label>
      <label>Type d’entité
        <select value={draft.entityType} onChange={(event) => change('entityType', event.target.value)}>
          <option value="">Tous les types</option>
          {ENTITY_TYPES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
      </label>
      <label>Identifiant d’entité
        <input value={draft.entityId} onChange={(event) => change('entityId', event.target.value)} placeholder="UUID exact (facultatif)" maxLength="36" />
      </label>
      <label>Acteur
        <select value={draft.actorId} onChange={(event) => change('actorId', event.target.value)}>
          <option value="">Tous les acteurs</option>
          {actors.map((actor) => <option value={actor.id} key={actor.id}>{actor.displayName}</option>)}
        </select>
      </label>
    </div>

    {moreActors && <button className="text-button audit-more-actors" type="button" onClick={onLoadMoreActors} disabled={loadingActors}>
      {loadingActors ? 'Chargement des acteurs…' : 'Charger plus d’acteurs'}
    </button>}
    {error && <p className="audit-filter-error" role="alert">{error}</p>}
    <div className="audit-filter-actions">
      <button className="secondary-button" type="button" onClick={reset}>Réinitialiser</button>
      <button className="primary-button" type="submit">Appliquer</button>
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
