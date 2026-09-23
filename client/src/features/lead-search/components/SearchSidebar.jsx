import {
  CircleDollarSign, Info, LoaderCircle, Search, Settings2, Sparkles, X,
} from '../../../icons'
import { Field, Toggle } from '../../../shared/ui/FormControls'


export function SearchSidebar({ copy, form, loading, mobilePanelOpen, onClose, onSubmit, onUpdate }) {
  return <>
    <aside id="search-panel" className={`sidebar ${mobilePanelOpen ? 'mobile-open' : ''}`}>
      <div className="search-panel-heading">
        <div><strong>{copy.settings}</strong><span>{copy.search}</span></div>
        <button className="sidebar-close" type="button" onClick={onClose} aria-label={copy.closeSettings}><X size={19} /></button>
      </div>

      <form onSubmit={onSubmit} className="search-form">
        <div className="sidebar-title">
          <span>{copy.search}</span>
          <Settings2 size={17} />
        </div>

        <Field id="search-query" label={copy.businessType} hint={copy.businessHint}>
          <div className="input-with-icon"><Search size={17} /><input id="search-query" value={form.query} onChange={(event) => onUpdate('query', event.target.value)} placeholder={copy.example} required /></div>
        </Field>

        <Field label={copy.centre}>
          <div className="coordinate-grid">
            <label><span>{copy.latitude}</span><input type="number" step="0.0001" min="-90" max="90" value={form.center_latitude} onChange={(event) => onUpdate('center_latitude', +event.target.value)} /></label>
            <label><span>{copy.longitude}</span><input type="number" step="0.0001" min="-180" max="180" value={form.center_longitude} onChange={(event) => onUpdate('center_longitude', +event.target.value)} /></label>
          </div>
        </Field>

        <Field id="search-radius" label={copy.radius} value={`${form.radius_km} km`}>
          <input id="search-radius" className="range" type="range" min="1" max="50" value={form.radius_km} onChange={(event) => onUpdate('radius_km', +event.target.value)} />
          <div className="range-labels"><span>1 km</span><span>50 km</span></div>
        </Field>

        <Toggle checked={form.include_service_area_businesses} onChange={(value) => onUpdate('include_service_area_businesses', value)} title={copy.serviceArea} description={copy.serviceAreaHelp} />

        <div className="call-estimate"><CircleDollarSign size={18} /><div><strong>{copy.apiCall}</strong><span>{copy.apiCallHelp}</span></div></div>

        <button className="primary-button" disabled={loading || !form.query.trim()}>
          {loading ? <><LoaderCircle className="spin" size={18} /> {copy.searching}</> : <><Sparkles size={18} /> {copy.searchBusinesses}</>}
        </button>
        <p className="form-footnote"><Info size={14} /> {copy.oneOff}</p>
      </form>
    </aside>
    {mobilePanelOpen && <button className="mobile-backdrop" type="button" onClick={onClose} aria-label={copy.closePanel} />}
  </>
}
