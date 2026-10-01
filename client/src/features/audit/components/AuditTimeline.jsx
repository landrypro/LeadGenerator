import { useState } from 'react'

import { actionLabel, entityTypeLabel, metadataRows, shortId } from '../catalog'


export function AuditTimeline({ audit, locale = 'fr-CA', timezone = 'UTC' }) {
  const copy = locale === 'en-CA' ? { loading: 'Loading activity log…', timeline: 'Timeline', event: 'event', events: 'events', loaded: 'loaded', refreshing: 'Refreshing…', refresh: 'Refresh', retry: 'Try again', empty: 'No event in this period.', hide: 'Hide details', show: 'Show details', loadMore: 'Load more', entity: 'Entity', noId: 'no identifier', correlation: 'Correlation reference', timestamp: 'UTC timestamp', unsupported: 'Details for this version cannot be displayed.', system: 'System', account: 'Account', loadingMore: 'Loading…' } : { loading: 'Chargement du journal…', timeline: 'Chronologie', event: 'événement', events: 'événements', loaded: 'chargé', refreshing: 'Actualisation…', refresh: 'Actualiser', retry: 'Réessayer', empty: 'Aucun événement dans cette période.', hide: 'Masquer les détails', show: 'Afficher les détails', loadMore: 'Charger la suite', entity: 'Entité', noId: 'sans identifiant', correlation: 'Référence de suivi', timestamp: 'Horodatage UTC', unsupported: 'Les détails de cette version ne peuvent pas être affichés.', system: 'Système', account: 'Compte', loadingMore: 'Chargement…' }
  const [expanded, setExpanded] = useState(() => new Set())

  function toggle(id) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (audit.loading) return <div className="administration-loading" role="status">{copy.loading}</div>

  return <section className="administration-card audit-results" aria-labelledby="audit-results-title">
    <div className="resource-list-heading">
      <div>
        <h2 id="audit-results-title">{copy.timeline}</h2>
        <p>{audit.items.length} {audit.items.length > 1 ? copy.events : copy.event} {copy.loaded}</p>
      </div>
      <button className="text-button" type="button" onClick={audit.refresh} disabled={audit.refreshing}>
        {audit.refreshing ? copy.refreshing : copy.refresh}
      </button>
    </div>
    <p className="sr-only" aria-live="polite">{audit.announcement}</p>
    {audit.error && <div className="error-banner compact" role="alert">
      <span>{audit.error}</span>
      <button className="text-button" type="button" onClick={audit.refresh}>{copy.retry}</button>
    </div>}
    {!audit.error && !audit.items.length
      ? <p className="administration-empty">{copy.empty}</p>
      : <ol className="audit-timeline">
        {audit.items.map((event) => {
          const isExpanded = expanded.has(event.id)
          const detailId = `audit-detail-${event.id}`
          return <li key={event.id}>
            <article>
              <div className="audit-marker" aria-hidden="true" />
              <div className="audit-event-summary">
                <div>
                  <h3>{actionLabel(event.action, locale)}</h3>
                  <p>{actorLabel(event.actor, copy)} · {entityTypeLabel(event.entity_type, locale)} {shortId(event.entity_id)}</p>
                </div>
                <time dateTime={event.occurred_at}>{formatDate(event.occurred_at, locale, timezone)}</time>
              </div>
              <button
                className="text-button audit-detail-button"
                type="button"
                aria-expanded={isExpanded}
                aria-controls={detailId}
                onClick={() => toggle(event.id)}
              >{isExpanded ? copy.hide : copy.show}</button>
              {isExpanded && <AuditDetail copy={copy} event={event} id={detailId} locale={locale} />}
            </article>
          </li>
        })}
      </ol>}
    {audit.nextCursor && <button className="secondary-button load-more-button" type="button" onClick={audit.loadMore} disabled={audit.loadingMore}>
      {audit.loadingMore ? copy.loadingMore : copy.loadMore}
    </button>}
  </section>
}


function AuditDetail({ copy, event, id, locale }) {
  const rows = metadataRows(event)
  return <div className="audit-detail" id={id}>
    <dl>
      {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      <div><dt>{copy.entity}</dt><dd>{entityTypeLabel(event.entity_type, locale)} · {event.entity_id ?? copy.noId}</dd></div>
      <div><dt>{copy.correlation}</dt><dd>{event.correlation_id}</dd></div>
      <div><dt>{copy.timestamp}</dt><dd>{new Date(event.occurred_at).toISOString()}</dd></div>
    </dl>
    {!rows.length && event.schema_version !== 1 && <p>{copy.unsupported}</p>}
  </div>
}


function actorLabel(actor, copy) {
  if (actor.kind === 'system') return copy.system
  return actor.display_name || `${copy.account} ${shortId(actor.id)}`
}


function formatDate(value, locale, timezone) {
  try {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: timezone,
    }).format(new Date(value))
  } catch {
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(value))
  }
}
