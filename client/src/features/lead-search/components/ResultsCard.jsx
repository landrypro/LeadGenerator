import { useEffect, useMemo, useRef, useState } from 'react'

import { Download, Search, X } from '../../../icons'
import { numberFormatter } from '../config'
import { leadSearchMessages } from '../messages'
import { EmptyState, LoadingRows, PlaceTable } from './LeadTable'


function SelectionToggle({ copy, selectedCount, selectablePlaces, prospectAdds }) {
  const checkboxRef = useRef(null)
  const selectableIds = selectablePlaces.map(place => place.place_id).filter(Boolean)
  const allSelected = selectableIds.length > 0 && selectableIds.every(placeId => prospectAdds?.selectedPlaceIds?.has(placeId))
  const partial = selectedCount > 0 && !allSelected

  useEffect(() => {
    if (checkboxRef.current) checkboxRef.current.indeterminate = partial
  }, [partial])

  if (!selectableIds.length) return null
  return <label className="selection-toggle">
    <input
      ref={checkboxRef}
      type="checkbox"
      checked={allSelected}
      onChange={() => prospectAdds?.togglePlaces(selectableIds)}
    />
    <span>{copy.selectAllDisplayed}</span>
  </label>
}

function addSelectedOrFocusAlias(prospectAdds) {
  const missingPlaceId = prospectAdds?.firstSelectedMissingAlias
  if (!missingPlaceId) return prospectAdds?.addSelected()
  document.getElementById(`crm-alias-${missingPlaceId}`)?.focus()
  return null
}

function SelectionAction({ copy, prospectAdds, className = '' }) {
  const count = prospectAdds?.selectedCount ?? 0
  if (!count) return null
  return <div className={`selection-action ${className}`} role="status" aria-live="polite">
    <span>{copy.selectedCount.replace('{count}', count)}</span>
    <button
      className="crm-add-selected"
      type="button"
      disabled={prospectAdds?.adding}
      onClick={() => addSelectedOrFocusAlias(prospectAdds)}
      title={!prospectAdds?.selectedReady ? copy.addSelectionTitle : undefined}
    >{copy.addSelection}</button>
  </div>
}

export function ResultsCard({ copy = leadSearchMessages['fr-CA'], places, result, loading, canCreateProspects = false, prospectAdds = null }) {
  const [filter, setFilter] = useState('')
  const visiblePlaces = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    return places.filter((place) => !needle || `${place.name} ${place.address} ${place.primary_type}`.toLowerCase().includes(needle))
  }, [places, filter])
  const selectablePlaces = visiblePlaces.filter((place) => !['created', 'existing'].includes(prospectAdds?.itemStates?.[place.place_id]))

  return <section className={`results-card ${result ? 'has-search' : 'is-ready'}`} aria-label={copy.googleResults}>
    <div className="results-header">
      <div><p className="eyebrow">{copy.temporary}</p><h2 id="search-results-heading" tabIndex="-1">{copy.businessesFound} <span>{numberFormatter.format(places.length)}</span></h2></div>
      <div className="results-actions">
        <button className="export-button" type="button" disabled aria-disabled="true" title={copy.exportTitle}><Download size={17} /> {copy.export}</button>
      </div>
    </div>

    <div className="table-tools">
      <div className="table-search"><Search size={16} /><label className="sr-only" htmlFor="places-filter">{copy.filter}</label><input id="places-filter" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder={copy.filterPlaceholder} />{filter && <button onClick={() => setFilter('')} aria-label={copy.clearFilter}><X size={15} /></button>}</div>
      {canCreateProspects && result?.selection_token && <SelectionToggle copy={copy} selectedCount={prospectAdds?.selectedCount ?? 0} selectablePlaces={selectablePlaces} prospectAdds={prospectAdds} />}
      <span className="visible-count">{visiblePlaces.length} {visiblePlaces.length > 1 ? copy.displayedPlural : copy.displayed}</span>
    </div>

    {loading ? <LoadingRows /> : visiblePlaces.length ? <PlaceTable
      places={visiblePlaces}
      canCreateProspects={canCreateProspects && !!result?.selection_token}
      prospectAdds={prospectAdds}
      copy={copy}
    /> : <EmptyState copy={copy} hasSearch={!!result} />}
    {canCreateProspects && result?.selection_token && <SelectionAction copy={copy} prospectAdds={prospectAdds} className="selection-action-bottom" />}
    <div className="google-attribution" aria-label="Attribution Google Maps" translate="no">Google Maps</div>
  </section>
}
