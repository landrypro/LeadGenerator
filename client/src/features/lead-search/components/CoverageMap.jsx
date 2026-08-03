import { AlertTriangle, LoaderCircle, MapPin, Target } from '../../../icons'
import { useMapSnapshot } from '../hooks/useMapSnapshot'


export function CoverageMap({ places, form, loading, searchedAt, resultToken, mapEnabled }) {
  const { snapshotUrl, snapshotLoading, snapshotError } = useMapSnapshot(
    searchedAt,
    mapEnabled ? resultToken : '',
  )

  return <div className="coverage-card">
    <div className="map-top"><div><p className="eyebrow">Aperçu de couverture</p><h2>Rayon de {form.radius_km} km</h2></div><div className="zone-pill"><Target size={14} /> 1 zone</div></div>
    <div className="map-canvas real-map">
      {snapshotUrl && !snapshotLoading && <img className="map-snapshot" src={snapshotUrl} alt={`Carte Google des ${places.length} entreprises trouvées dans un rayon de ${form.radius_km} kilomètres`} />}
      {!searchedAt && !loading && <div className="map-pending"><div><MapPin size={24} /><span /></div><strong>Carte Google après la recherche</strong><small>La capture réelle et les établissements trouvés apparaîtront ici.</small></div>}
      {snapshotLoading && <div className="map-pending"><LoaderCircle className="spin" size={25} /><strong>Création de la carte Google…</strong></div>}
      {snapshotError && !snapshotLoading && <div className="map-pending map-error"><AlertTriangle size={23} /><strong>Carte non disponible</strong><small>{snapshotError}</small></div>}
      {loading && <div className="scan"><span /></div>}
    </div>
  </div>
}
