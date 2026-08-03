import {
  CircleDollarSign, Info, LoaderCircle, Search, Settings2, Sparkles, X,
} from '../../../icons'
import { Field, Toggle } from '../../../shared/ui/FormControls'


export function SearchSidebar({ form, loading, mobilePanelOpen, onClose, onSubmit, onUpdate }) {
  return <>
    <aside id="search-panel" className={`sidebar ${mobilePanelOpen ? 'mobile-open' : ''}`}>
      <div className="search-panel-heading">
        <div><strong>Paramètres</strong><span>Recherche Google</span></div>
        <button className="sidebar-close" type="button" onClick={onClose} aria-label="Fermer les paramètres"><X size={19} /></button>
      </div>

      <form onSubmit={onSubmit} className="search-form">
        <div className="sidebar-title">
          <span>Recherche Google</span>
          <Settings2 size={17} />
        </div>

        <Field id="search-query" label="Type d’entreprise" hint="Gardez un terme simple, sans ville.">
          <div className="input-with-icon"><Search size={17} /><input id="search-query" value={form.query} onChange={(event) => onUpdate('query', event.target.value)} placeholder="Ex. plombier" required /></div>
        </Field>

        <Field label="Centre de la recherche">
          <div className="coordinate-grid">
            <label><span>Latitude</span><input type="number" step="0.0001" min="-90" max="90" value={form.center_latitude} onChange={(event) => onUpdate('center_latitude', +event.target.value)} /></label>
            <label><span>Longitude</span><input type="number" step="0.0001" min="-180" max="180" value={form.center_longitude} onChange={(event) => onUpdate('center_longitude', +event.target.value)} /></label>
          </div>
        </Field>

        <Field id="search-radius" label="Rayon de recherche" value={`${form.radius_km} km`}>
          <input id="search-radius" className="range" type="range" min="1" max="50" value={form.radius_km} onChange={(event) => onUpdate('radius_km', +event.target.value)} />
          <div className="range-labels"><span>1 km</span><span>50 km</span></div>
        </Field>

        <Toggle checked={form.include_service_area_businesses} onChange={(value) => onUpdate('include_service_area_businesses', value)} title="Entreprises de zone de service" description="Inclure celles qui n’affichent pas d’adresse" />

        <div className="call-estimate"><CircleDollarSign size={18} /><div><strong>1 appel Google par recherche</strong><span>20 résultats maximum, sans champs de contact</span></div></div>

        <button className="primary-button" disabled={loading || !form.query.trim()}>
          {loading ? <><LoaderCircle className="spin" size={18} /> Recherche en cours…</> : <><Sparkles size={18} /> Rechercher des établissements</>}
        </button>
        <p className="form-footnote"><Info size={14} /> Recherche ponctuelle, sans pagination automatique.</p>
      </form>
    </aside>
    {mobilePanelOpen && <button className="mobile-backdrop" type="button" onClick={onClose} aria-label="Fermer le panneau de recherche" />}
  </>
}
