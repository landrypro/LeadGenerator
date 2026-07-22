import { AlertTriangle, LoaderCircle, MapPin, Target } from '../../../icons'
import { useMapSnapshot } from '../hooks/useMapSnapshot'


export function CoverageMap({ leads, form, loading, generatedAt, resultToken }) {
  const { snapshotUrl, snapshotLoading, snapshotError } = useMapSnapshot(generatedAt, resultToken)

  return <div className="coverage-card">
    <div className="map-top"><div><p className="eyebrow">Aperçu de couverture</p><h2>Rayon de {form.radius_km} km</h2></div><div className="zone-pill"><Target size={14} /> {form.max_tiles} zones</div></div>
    <div className="map-canvas real-map">
      {snapshotUrl && !snapshotLoading && <img className="map-snapshot" src={snapshotUrl} alt={`Carte Google des ${leads.length} entreprises trouvées dans un rayon de ${form.radius_km} kilomètres`} />}
      {!generatedAt && !loading && <div className="map-pending"><div><MapPin size={24} /><span /></div><strong>Carte Google après génération</strong><small>La capture réelle et les entreprises trouvées apparaîtront ici.</small></div>}
      {snapshotLoading && <div className="map-pending"><LoaderCircle className="spin" size={25} /><strong>Création de la carte Google…</strong></div>}
      {snapshotError && !snapshotLoading && <div className="map-pending map-error"><AlertTriangle size={23} /><strong>Carte non disponible</strong><small>{snapshotError}</small></div>}
      {loading && <div className="scan"><span /></div>}
    </div>
  </div>
}
