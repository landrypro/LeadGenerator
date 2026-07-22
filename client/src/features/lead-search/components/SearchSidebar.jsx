import {
  ChevronDown, CircleDollarSign, Info, LoaderCircle, MapPin, Search, Settings2, Sparkles, X,
} from '../../../icons'
import { Field, Toggle } from '../../../shared/ui/FormControls'


export function SearchSidebar({ form, loading, mobilePanelOpen, onClose, onSubmit, onUpdate }) {
  const projectedCalls = form.max_tiles * form.max_pages

  return <>
    <aside id="search-panel" className={`sidebar ${mobilePanelOpen ? 'mobile-open' : ''}`}>
      <div className="brand">
        <div className="brand-mark"><MapPin size={21} strokeWidth={2.5} /></div>
        <div><strong>Prospect</strong><span>Lead intelligence</span></div>
        <button className="sidebar-close" type="button" onClick={onClose} aria-label="Fermer les paramètres"><X size={19} /></button>
      </div>

      <form onSubmit={onSubmit} className="search-form">
        <div className="sidebar-title">
          <span>Nouvelle recherche</span>
          <Settings2 size={17} />
        </div>

        <Field label="Type d’entreprise" hint="Gardez un terme simple, sans ville.">
          <div className="input-with-icon"><Search size={17} /><input value={form.query} onChange={(event) => onUpdate('query', event.target.value)} placeholder="Ex. plombier" required /></div>
        </Field>

        <Field label="Centre de la recherche">
          <div className="coordinate-grid">
            <label><span>Latitude</span><input type="number" step="0.0001" min="-90" max="90" value={form.center_latitude} onChange={(event) => onUpdate('center_latitude', +event.target.value)} /></label>
            <label><span>Longitude</span><input type="number" step="0.0001" min="-180" max="180" value={form.center_longitude} onChange={(event) => onUpdate('center_longitude', +event.target.value)} /></label>
          </div>
        </Field>

        <Field label="Rayon global" value={`${form.radius_km} km`}>
          <input className="range" type="range" min="1" max="50" value={form.radius_km} onChange={(event) => onUpdate('radius_km', +event.target.value)} />
          <div className="range-labels"><span>1 km</span><span>50 km</span></div>
        </Field>

        <div className="form-row">
          <Field label="Objectif"><input type="number" min="1" max="500" value={form.target} onChange={(event) => onUpdate('target', +event.target.value)} /></Field>
          <Field label="Zones"><input type="number" min="1" max="30" value={form.max_tiles} onChange={(event) => onUpdate('max_tiles', +event.target.value)} /></Field>
          <Field label="Pages / zone"><div className="select-wrap"><select value={form.max_pages} onChange={(event) => onUpdate('max_pages', +event.target.value)}><option value="1">1</option><option value="2">2</option><option value="3">3</option></select><ChevronDown size={15} /></div></Field>
        </div>

        <Toggle checked={form.contact_fields} onChange={(value) => onUpdate('contact_fields', value)} title="Téléphone et site Web" description="Champs de contact facturés à un niveau supérieur" accent />
        <Toggle checked={form.include_service_area_businesses} onChange={(value) => onUpdate('include_service_area_businesses', value)} title="Entreprises de zone de service" description="Inclure celles qui n’affichent pas d’adresse" />

        <div className="call-estimate"><CircleDollarSign size={18} /><div><strong>Jusqu’à {projectedCalls} appels API</strong><span>{form.contact_fields ? 'Champs de contact activés' : 'Mode économique sans contacts'}</span></div></div>

        <button className="primary-button" disabled={loading || !form.query.trim()}>
          {loading ? <><LoaderCircle className="spin" size={18} /> Recherche en cours…</> : <><Sparkles size={18} /> Générer les leads</>}
        </button>
        <p className="form-footnote"><Info size={14} /> Objectif d’arrêt, sans garantie d’exhaustivité.</p>
      </form>
    </aside>
    {mobilePanelOpen && <button className="mobile-backdrop" type="button" onClick={onClose} aria-label="Fermer le panneau de recherche" />}
  </>
}
