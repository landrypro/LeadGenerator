import { AlertTriangle, LoaderCircle, MapPin, Target } from '../../../icons'
import { useMapSnapshot } from '../hooks/useMapSnapshot'


export function CoverageMap({ copy, places, form, loading, searchedAt, resultToken, mapEnabled }) {
  const { snapshotUrl, snapshotLoading, snapshotError } = useMapSnapshot(
    searchedAt,
    mapEnabled ? resultToken : '',
  )

  return <div className="coverage-card">
    <div className="map-top"><div><p className="eyebrow">{copy.coverage}</p><h2>{copy.radiusOf.replace('{radius}', form.radius_km)}</h2></div><div className="zone-pill"><Target size={14} /> {copy.oneZone}</div></div>
    <div className="map-canvas real-map">
      {snapshotUrl && !snapshotLoading && <img className="map-snapshot" src={snapshotUrl} alt={copy.mapAlt.replace('{count}', places.length).replace('{radius}', form.radius_km)} />}
      {!searchedAt && !loading && <div className="map-pending"><div><MapPin size={24} /><span /></div><strong>{copy.mapPending}</strong><small>{copy.mapPendingHelp}</small></div>}
      {snapshotLoading && <div className="map-pending"><LoaderCircle className="spin" size={25} /><strong>{copy.mapLoading}</strong></div>}
      {snapshotError && !snapshotLoading && <div className="map-pending map-error"><AlertTriangle size={23} /><strong>{copy.mapUnavailable}</strong><small>{snapshotError}</small></div>}
      {loading && <div className="scan"><span /></div>}
    </div>
  </div>
}
