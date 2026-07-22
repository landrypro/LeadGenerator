import { Building2, ExternalLink, Globe2, MapPin, Phone, Search } from '../../../icons'


function formatType(value) {
  return value ? value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase()) : 'Entreprise locale'
}


export function LeadTable({ leads }) {
  return <div className="table-wrap"><table><thead><tr><th>Entreprise</th><th>Contact</th><th>Localisation</th><th>Distance</th><th>Statut</th><th><span className="sr-only">Ouvrir</span></th></tr></thead><tbody>
    {leads.map((lead, index) => <tr key={lead.place_id || `${lead.name}-${index}`}>
      <td><div className="company-cell"><div className="company-avatar">{lead.name?.slice(0, 1).toUpperCase() || <Building2 size={16} />}</div><div><strong>{lead.name || 'Sans nom'}</strong><span>{formatType(lead.primary_type)}</span></div></div></td>
      <td><div className="contact-cell">{lead.phone ? <a href={`tel:${lead.phone}`}><Phone size={14} />{lead.phone}</a> : <span className="muted">Téléphone non demandé</span>}{lead.website && <a href={lead.website} target="_blank" rel="noreferrer"><Globe2 size={14} />Site Web</a>}</div></td>
      <td><div className="address-cell"><MapPin size={15} /><span>{lead.address || 'Zone de service — adresse masquée'}</span></div></td>
      <td>{lead.radius_verified ? <span className="distance">{lead.distance_km?.toLocaleString('fr-CA')} km</span> : <span className="unverified">Non vérifiable</span>}</td>
      <td><span className={`status-badge ${lead.business_status === 'OPERATIONAL' ? 'active' : ''}`}><i />{lead.business_status === 'OPERATIONAL' ? 'Ouvert' : lead.business_status || 'Inconnu'}</span></td>
      <td>{lead.google_maps_url && <a className="open-link" href={lead.google_maps_url} target="_blank" rel="noreferrer" aria-label={`Ouvrir ${lead.name} dans Google Maps`}><ExternalLink size={16} /></a>}</td>
    </tr>)}
  </tbody></table></div>
}


export function EmptyState({ hasSearch }) {
  return <div className="empty-state"><div className="empty-illustration"><Search size={26} /><span /><i /></div><h3>{hasSearch ? 'Aucun résultat pour ce filtre' : 'Prêt à trouver vos prochains clients'}</h3><p>{hasSearch ? 'Modifiez les filtres pour afficher davantage d’entreprises.' : 'Configurez votre zone et lancez une première recherche. Commencez petit pour maîtriser les coûts.'}</p></div>
}


export function LoadingRows() {
  return <div className="loading-rows">{[1, 2, 3, 4].map((row) => <div className="loading-row" key={row}><i /><span /><span /><span /></div>)}</div>
}
