import { Building2, Check, ExternalLink, MapPin, Search } from '../../../icons'


function formatType(value, copy) {
  return value ? value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase()) : copy.localBusiness
}


function actionLabel(state, adding, copy) {
  if (adding) return copy.adding
  if (state === 'created') return copy.added
  if (state === 'existing') return copy.existing
  if (state === 'error') return copy.retry
  return copy.add
}


export function PlaceTable({ copy, places, canCreateProspects = false, prospectAdds = null }) {
  return <div className="table-wrap"><table><thead><tr>{canCreateProspects && <th><span className="sr-only">{copy.select}</span></th>}<th>{copy.company}</th><th>{copy.placeId}</th><th>{copy.location}</th><th>{copy.distance}</th><th>{copy.status}</th>{canCreateProspects && <th>{copy.crmName}</th>}<th><span className="sr-only">{copy.open}</span></th></tr></thead><tbody>
    {places.map((place, index) => {
      const state = prospectAdds?.itemStates?.[place.place_id]
      const adding = prospectAdds?.addingIds?.has(place.place_id)
      const alias = prospectAdds?.internalAliases?.[place.place_id] ?? ''
      const added = ['created', 'existing'].includes(state)
      return <tr key={place.place_id || `${place.name}-${index}`}>
      {canCreateProspects && <td className="place-selection-cell"><input
        className="place-select"
        type="checkbox"
        aria-label={copy.selectPlace.replace('{name}', place.name || copy.unnamedPlace)}
        checked={prospectAdds?.selectedPlaceIds?.has(place.place_id) ?? false}
        disabled={adding || added}
        onChange={() => prospectAdds?.togglePlace(place.place_id)}
      /></td>}
      <td className="place-company-cell"><div className="company-cell"><div className="company-avatar">{place.name?.slice(0, 1).toUpperCase() || <Building2 size={16} />}</div><div><strong>{place.name || copy.noName}</strong><span>{formatType(place.primary_type, copy)}</span></div></div></td>
      <td className="place-id-cell"><code title={place.place_id}>{place.place_id}</code></td>
      <td className="place-address-cell"><div className="address-cell"><MapPin size={15} /><span>{place.address || copy.hiddenAddress}</span></div></td>
      <td className="place-distance-cell">{place.radius_verified ? <span className="distance">{place.distance_km?.toLocaleString('fr-CA')} km</span> : <span className="unverified">{copy.unverified}</span>}</td>
      <td className="place-status-cell"><span className={`status-badge ${place.business_status === 'OPERATIONAL' ? 'active' : ''}`}><i />{place.business_status === 'OPERATIONAL' ? copy.opened : place.business_status || copy.unknown}</span></td>
      {canCreateProspects && <td className="place-crm-cell"><div className="crm-alias-action">
        <label className="sr-only" htmlFor={`crm-alias-${index}`}>{copy.crmNameFor.replace('{name}', place.name || copy.unnamedPlace)}</label>
        <input
          id={`crm-alias-${index}`}
          className="crm-alias-input"
          value={alias}
          onChange={(event) => prospectAdds?.updateInternalAlias(place.place_id, event.target.value)}
          placeholder={copy.crmNamePlaceholder}
          maxLength="160"
          disabled={adding || added}
          required
        />
        <button
        className={`crm-add-button ${prospectAdds?.itemStates?.[place.place_id] || ''}`}
        type="button"
        disabled={adding || added || !alias.trim()}
        onClick={() => prospectAdds?.addOne(place.place_id)}
      >{added && <Check size={13} />}{actionLabel(state, adding, copy)}</button>
      </div></td>}
      <td className="place-external-cell">{place.google_maps_url && <a className="open-link" href={place.google_maps_url} target="_blank" rel="noopener noreferrer" aria-label={copy.openInMaps.replace('{name}', place.name || copy.unnamedPlace)}><ExternalLink size={16} /></a>}</td>
    </tr>})}
  </tbody></table></div>
}


export function EmptyState({ copy, hasSearch }) {
  return <div className="empty-state"><div className="empty-illustration"><Search size={26} /><span /><i /></div><h3>{hasSearch ? copy.noResults : copy.ready}</h3><p>{hasSearch ? copy.noResultsHelp : copy.readyHelp}</p></div>
}


export function LoadingRows() {
  return <div className="loading-rows">{[1, 2, 3, 4].map((row) => <div className="loading-row" key={row}><i /><span /><span /><span /></div>)}</div>
}
