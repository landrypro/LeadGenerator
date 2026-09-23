import { useMemo, useState } from 'react'

import { Download, Search, X } from '../../../icons'
import { numberFormatter } from '../config'
import { leadSearchMessages } from '../messages'
import { EmptyState, LoadingRows, PlaceTable } from './LeadTable'


export function ResultsCard({ copy = leadSearchMessages['fr-CA'], places, result, loading, canCreateProspects = false, prospectAdds = null }) {
  const [filter, setFilter] = useState('')
  const visiblePlaces = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    return places.filter((place) => !needle || `${place.name} ${place.address} ${place.primary_type}`.toLowerCase().includes(needle))
  }, [places, filter])

  return <section className="results-card" aria-label={copy.googleResults}>
    <div className="results-header">
      <div><p className="eyebrow">{copy.temporary}</p><h2>{copy.businessesFound} <span>{numberFormatter.format(places.length)}</span></h2></div>
      <div className="results-actions">
        {canCreateProspects && result?.selection_token && <button
          className="crm-add-selected"
          type="button"
          disabled={!prospectAdds?.selectedReady || prospectAdds?.adding}
          onClick={prospectAdds?.addSelected}
          title={prospectAdds?.selectedCount && !prospectAdds?.selectedReady ? copy.addSelectionTitle : undefined}
        >{copy.addSelection} {prospectAdds?.selectedCount ? `(${prospectAdds.selectedCount})` : ''}</button>}
        <button className="export-button" type="button" disabled aria-disabled="true" title={copy.exportTitle}><Download size={17} /> {copy.export}</button>
      </div>
    </div>

    <div className="table-tools">
      <div className="table-search"><Search size={16} /><label className="sr-only" htmlFor="places-filter">{copy.filter}</label><input id="places-filter" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder={copy.filterPlaceholder} />{filter && <button onClick={() => setFilter('')} aria-label={copy.clearFilter}><X size={15} /></button>}</div>
      <span className="visible-count">{visiblePlaces.length} {visiblePlaces.length > 1 ? copy.displayedPlural : copy.displayed}</span>
    </div>

    {loading ? <LoadingRows /> : visiblePlaces.length ? <PlaceTable
      places={visiblePlaces}
      canCreateProspects={canCreateProspects && !!result?.selection_token}
      prospectAdds={prospectAdds}
      copy={copy}
    /> : <EmptyState copy={copy} hasSearch={!!result} />}
    <div className="google-attribution" aria-label="Attribution Google Maps" translate="no">Google Maps</div>
  </section>
}
