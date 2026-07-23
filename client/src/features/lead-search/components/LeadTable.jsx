import { Building2, ExternalLink, MapPin, Search } from '../../../icons'


function formatType(value) {
  return value ? value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase()) : 'Entreprise locale'
}


export function PlaceTable({ places }) {
  return <div className="table-wrap"><table><thead><tr><th>Entreprise</th><th>Localisation</th><th>Distance</th><th>Statut</th><th><span className="sr-only">Ouvrir</span></th></tr></thead><tbody>
    {places.map((place, index) => <tr key={place.place_id || `${place.name}-${index}`}>
      <td><div className="company-cell"><div className="company-avatar">{place.name?.slice(0, 1).toUpperCase() || <Building2 size={16} />}</div><div><strong>{place.name || 'Sans nom'}</strong><span>{formatType(place.primary_type)}</span></div></div></td>
      <td><div className="address-cell"><MapPin size={15} /><span>{place.address || 'Zone de service — adresse masquée'}</span></div></td>
      <td>{place.radius_verified ? <span className="distance">{place.distance_km?.toLocaleString('fr-CA')} km</span> : <span className="unverified">Non vérifiable</span>}</td>
      <td><span className={`status-badge ${place.business_status === 'OPERATIONAL' ? 'active' : ''}`}><i />{place.business_status === 'OPERATIONAL' ? 'Ouvert' : place.business_status || 'Inconnu'}</span></td>
      <td>{place.google_maps_url && <a className="open-link" href={place.google_maps_url} target="_blank" rel="noopener noreferrer" aria-label={`Ouvrir ${place.name} dans Google Maps`}><ExternalLink size={16} /></a>}</td>
    </tr>)}
  </tbody></table></div>
}


export function EmptyState({ hasSearch }) {
  return <div className="empty-state"><div className="empty-illustration"><Search size={26} /><span /><i /></div><h3>{hasSearch ? 'Aucun résultat pour ce filtre' : 'Prêt à rechercher des établissements'}</h3><p>{hasSearch ? 'Modifiez le filtre ou la zone pour afficher d’autres entreprises.' : 'Configurez votre zone et lancez une recherche ponctuelle. Vingt résultats au maximum seront affichés.'}</p></div>
}


export function LoadingRows() {
  return <div className="loading-rows">{[1, 2, 3, 4].map((row) => <div className="loading-row" key={row}><i /><span /><span /><span /></div>)}</div>
}
