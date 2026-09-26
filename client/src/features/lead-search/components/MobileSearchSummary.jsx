function locationDescription(appliedSearch, copy) {
  const location = appliedSearch?.location
  const form = appliedSearch?.form
  if (!form) return ''
  const centre = location?.locality || location?.area || `${form.center_latitude}, ${form.center_longitude}`
  return `${centre} · ${form.radius_km} km · ${form.include_service_area_businesses ? copy.serviceAreaIncluded : copy.serviceAreaExcluded}`
}

export function MobileSearchSummary({ copy, appliedSearch, mapExpanded, onEdit, onToggleMap }) {
  const hasAppliedSearch = Boolean(appliedSearch)
  return <section className={`mobile-search-summary ${hasAppliedSearch ? 'has-search' : ''}`} aria-label={copy.appliedSearch}>
    {hasAppliedSearch ? <>
      <p className="eyebrow">{copy.appliedSearch}</p>
      <h2>{appliedSearch.form.query}</h2>
      <p>{locationDescription(appliedSearch, copy)}</p>
      <div className="mobile-search-summary-actions">
        <button type="button" className="secondary-button" onClick={onEdit}>{copy.editParameters}</button>
        <button type="button" className="secondary-button" onClick={onToggleMap} aria-expanded={mapExpanded} aria-controls="search-overview-secondary">
          {mapExpanded ? copy.hideMap : copy.viewMap}
        </button>
      </div>
    </> : <>
      <p className="eyebrow">{copy.search}</p>
      <h2>{copy.readyToConfigure}</h2>
      <p>{copy.readyToConfigureHelp}</p>
      <button type="button" className="primary-button" onClick={onEdit}>{copy.defineParameters}</button>
      <small>{copy.callEstimateTitle}</small>
    </>}
  </section>
}
