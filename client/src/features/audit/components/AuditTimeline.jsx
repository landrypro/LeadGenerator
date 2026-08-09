import { useState } from 'react'

import { actionLabel, entityTypeLabel, metadataRows, shortId } from '../catalog'


export function AuditTimeline({ audit, timezone = 'UTC' }) {
  const [expanded, setExpanded] = useState(() => new Set())

  function toggle(id) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (audit.loading) return <div className="administration-loading" role="status">Chargement du journal…</div>

  return <section className="administration-card audit-results" aria-labelledby="audit-results-title">
    <div className="resource-list-heading">
      <div>
        <h2 id="audit-results-title">Chronologie</h2>
        <p>{audit.items.length} événement{audit.items.length > 1 ? 's' : ''} chargé{audit.items.length > 1 ? 's' : ''}</p>
      </div>
      <button className="text-button" type="button" onClick={audit.refresh} disabled={audit.refreshing}>
        {audit.refreshing ? 'Actualisation…' : 'Actualiser'}
      </button>
    </div>
    <p className="sr-only" aria-live="polite">{audit.announcement}</p>
    {audit.error && <div className="error-banner compact" role="alert">
      <span>{audit.error}</span>
      <button className="text-button" type="button" onClick={audit.refresh}>Réessayer</button>
    </div>}
    {!audit.error && !audit.items.length
      ? <p className="administration-empty">Aucun événement dans cette période.</p>
      : <ol className="audit-timeline">
        {audit.items.map((event) => {
          const isExpanded = expanded.has(event.id)
          const detailId = `audit-detail-${event.id}`
          return <li key={event.id}>
            <article>
              <div className="audit-marker" aria-hidden="true" />
              <div className="audit-event-summary">
                <div>
                  <h3>{actionLabel(event.action)}</h3>
                  <p>{actorLabel(event.actor)} · {entityTypeLabel(event.entity_type)} {shortId(event.entity_id)}</p>
                </div>
                <time dateTime={event.occurred_at}>{formatDate(event.occurred_at, timezone)}</time>
              </div>
              <button
                className="text-button audit-detail-button"
                type="button"
                aria-expanded={isExpanded}
                aria-controls={detailId}
                onClick={() => toggle(event.id)}
              >{isExpanded ? 'Masquer les détails' : 'Afficher les détails'}</button>
              {isExpanded && <AuditDetail event={event} id={detailId} />}
            </article>
          </li>
        })}
      </ol>}
    {audit.nextCursor && <button className="secondary-button load-more-button" type="button" onClick={audit.loadMore} disabled={audit.loadingMore}>
      {audit.loadingMore ? 'Chargement…' : 'Charger la suite'}
    </button>}
  </section>
}


function AuditDetail({ event, id }) {
  const rows = metadataRows(event)
  return <div className="audit-detail" id={id}>
    <dl>
      {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      <div><dt>Entité</dt><dd>{entityTypeLabel(event.entity_type)} · {event.entity_id ?? 'sans identifiant'}</dd></div>
      <div><dt>Référence de suivi</dt><dd>{event.correlation_id}</dd></div>
      <div><dt>Horodatage UTC</dt><dd>{new Date(event.occurred_at).toISOString()}</dd></div>
    </dl>
    {!rows.length && event.schema_version !== 1 && <p>Les détails de cette version ne peuvent pas être affichés.</p>}
  </div>
}


function actorLabel(actor) {
  if (actor.kind === 'system') return 'Système'
  return actor.display_name || `Compte ${shortId(actor.id)}`
}


function formatDate(value, timezone) {
  try {
    return new Intl.DateTimeFormat('fr-CA', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: timezone,
    }).format(new Date(value))
  } catch {
    return new Intl.DateTimeFormat('fr-CA', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(value))
  }
}
