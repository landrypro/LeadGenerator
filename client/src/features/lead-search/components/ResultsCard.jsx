import { useMemo, useState } from 'react'

import { Download, Search, X } from '../../../icons'
import { numberFormatter } from '../config'
import { EmptyState, LoadingRows, PlaceTable } from './LeadTable'


export function ResultsCard({ places, result, loading }) {
  const [filter, setFilter] = useState('')
  const visiblePlaces = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    return places.filter((place) => !needle || `${place.name} ${place.address} ${place.primary_type}`.toLowerCase().includes(needle))
  }, [places, filter])

  return <section className="results-card" aria-label="Résultats Google Maps">
    <div className="results-header">
      <div><p className="eyebrow">Résultats temporaires</p><h2>Établissements trouvés <span>{numberFormatter.format(places.length)}</span></h2></div>
      <button className="export-button" type="button" disabled aria-disabled="true" title="L’export des données Google Maps est désactivé"><Download size={17} /> Exporter Excel</button>
    </div>

    <div className="table-tools">
      <div className="table-search"><Search size={16} /><input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filtrer par nom, ville ou activité…" />{filter && <button onClick={() => setFilter('')} aria-label="Effacer le filtre"><X size={15} /></button>}</div>
      <span className="visible-count">{visiblePlaces.length} affiché{visiblePlaces.length > 1 ? 's' : ''}</span>
    </div>

    {loading ? <LoadingRows /> : visiblePlaces.length ? <PlaceTable places={visiblePlaces} /> : <EmptyState hasSearch={!!result} />}
    <div className="google-attribution" aria-label="Attribution Google Maps" translate="no">Google Maps</div>
  </section>
}
