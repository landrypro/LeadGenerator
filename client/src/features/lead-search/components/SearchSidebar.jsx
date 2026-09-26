import { useEffect, useRef } from 'react'

import {
  CircleDollarSign, Info, LoaderCircle, Search, Settings2, Sparkles, X,
} from '../../../icons'
import { Field, Toggle } from '../../../shared/ui/FormControls'
import { LocationAutocomplete } from './LocationAutocomplete'


function getFocusableElements(container) {
  return [...container.querySelectorAll('button:not([disabled]), input:not([disabled]), a[href], select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
}

export function SearchSidebar({ appliedSearch, copy, form, loading, mobilePanelOpen, onCancel, onClose, onSubmit, onUpdate, locale, location, onLocationChange, onLocationSelect, manualMode, onManualMode }) {
  const panelRef = useRef(null)
  const closeButtonRef = useRef(null)

  useEffect(() => {
    if (mobilePanelOpen) closeButtonRef.current?.focus()
  }, [mobilePanelOpen])

  useEffect(() => {
    if (!mobilePanelOpen) return undefined
    const background = [
      document.querySelector('.skip-link'),
      document.querySelector('.authenticated-header'),
      document.querySelector('.route-breadcrumb'),
      document.querySelector('.authenticated-mobile-navigation'),
    ].filter(Boolean)
    const previouslyInert = new Map(background.map(node => [node, node.hasAttribute('inert')]))
    background.forEach(node => node.setAttribute('inert', ''))
    return () => background.forEach(node => {
      if (!previouslyInert.get(node)) node.removeAttribute('inert')
    })
  }, [mobilePanelOpen])

  function trapFocus(event) {
    if (!mobilePanelOpen || event.key !== 'Tab') return
    const focusable = getFocusableElements(panelRef.current)
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      event.preventDefault()
      onClose()
      return
    }
    trapFocus(event)
  }

  return <>
    <aside
      id="search-panel"
      ref={panelRef}
      className={`sidebar ${mobilePanelOpen ? 'mobile-open' : ''}`}
      role={mobilePanelOpen ? 'dialog' : undefined}
      aria-modal={mobilePanelOpen || undefined}
      aria-labelledby="search-panel-title"
      onKeyDown={handleKeyDown}
    >
      <div className="search-panel-heading">
        <div><strong id="search-panel-title">{copy.settings}</strong><span>{copy.search}</span></div>
        <button ref={closeButtonRef} className="sidebar-close" type="button" onClick={onClose} aria-label={copy.closeSettings}><X size={19} /></button>
      </div>

      <form onSubmit={onSubmit} className="search-form">
        {appliedSearch && <p className="search-draft-notice" role="status">{copy.draftNotice}</p>}
        <div className="sidebar-title">
          <span>{copy.search}</span>
          <Settings2 size={17} />
        </div>

        <Field id="search-query" label={copy.businessType} hint={copy.businessHint}>
          <div className="input-with-icon"><Search size={17} /><input id="search-query" value={form.query} onChange={(event) => onUpdate('query', event.target.value)} placeholder={copy.example} required /></div>
        </Field>

        <Field label={copy.centre}>
          <LocationAutocomplete id="search-area" label={copy.area} hint={copy.areaHint}
            value={location.area} selected={location.areaSelected} scope="area" locale={locale} copy={copy}
            onChange={(value) => onLocationChange('area', value)} onSelect={(value) => onLocationSelect('area', value)} />
          <LocationAutocomplete id="search-locality" label={copy.locality} hint={copy.localityHint}
            value={location.locality} selected={location.localitySelected} area={location.areaSelected ? location.area : ''}
            countryCode={location.areaCountry || ''} disabled={!location.areaSelected}
            scope="locality" locale={locale} copy={copy}
            onChange={(value) => onLocationChange('locality', value)} onSelect={(value) => onLocationSelect('locality', value)} />
          {location.localitySelected && !manualMode && <small className="selected-location">{copy.centerResolved}: {form.center_latitude.toFixed(4)}, {form.center_longitude.toFixed(4)}</small>}
          <button className="coordinate-toggle" type="button" aria-expanded={manualMode} onClick={() => onManualMode(!manualMode)}>{copy.advancedCoordinates}</button>
          {manualMode && <div className="coordinate-grid">
            <label><span>{copy.latitude}</span><input type="number" required step="0.0001" min="-90" max="90" value={form.center_latitude} onChange={(event) => onUpdate('center_latitude', event.target.value === '' ? '' : +event.target.value)} /></label>
            <label><span>{copy.longitude}</span><input type="number" required step="0.0001" min="-180" max="180" value={form.center_longitude} onChange={(event) => onUpdate('center_longitude', event.target.value === '' ? '' : +event.target.value)} /></label>
          </div>}
        </Field>

        <Field id="search-radius" label={copy.radius} value={`${form.radius_km} km`}>
          <input id="search-radius" className="range" type="range" min="1" max="50" value={form.radius_km} onChange={(event) => onUpdate('radius_km', +event.target.value)} />
          <div className="range-labels"><span>1 km</span><span>50 km</span></div>
        </Field>

        <Toggle checked={form.include_service_area_businesses} onChange={(value) => onUpdate('include_service_area_businesses', value)} title={copy.serviceArea} description={copy.serviceAreaHelp} />

        <div className="call-estimate"><CircleDollarSign size={18} /><div><strong>{copy.callEstimateTitle}</strong><span>{copy.callEstimateHelp}</span></div></div>

        <div className="search-form-actions">
          <button className="secondary-button search-cancel" type="button" onClick={onCancel}>{copy.cancel}</button>
          <button className="primary-button" disabled={loading || !form.query.trim() || (!manualMode && !(location.areaSelected && location.localitySelected))}>
            {loading ? <><LoaderCircle className="spin" size={18} /> {copy.searching}</> : <><Sparkles size={18} /> {copy.searchBusinesses}</>}
          </button>
        </div>
        <p className="form-footnote"><Info size={14} /> {copy.oneOff}</p>
      </form>
    </aside>
    {mobilePanelOpen && <button className="mobile-backdrop" type="button" onClick={onClose} aria-label={copy.closePanel} />}
  </>
}
