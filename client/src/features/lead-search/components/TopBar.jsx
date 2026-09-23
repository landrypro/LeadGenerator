import { Settings2 } from '../../../icons'


export function TopBar({ copy, keyReady, mobilePanelOpen, onOpenSettings }) {
  return <header className="topbar">
    <div className="topbar-heading">
      <button className="mobile-controls-button" type="button" onClick={onOpenSettings} aria-expanded={mobilePanelOpen} aria-controls="search-panel" aria-label={copy.openSettings}><Settings2 size={17} /><span>{copy.settings}</span></button>
      <div><p className="eyebrow">Google Places API (New)</p><h1>{copy.title}</h1></div>
    </div>
    <div className="topbar-actions">
      <div className={`api-status ${keyReady ? 'ready' : ''}`} title={keyReady ? copy.apiReady : copy.apiMissing}><span />{keyReady === null ? copy.checking : keyReady ? copy.apiReady : copy.apiMissing}</div>
    </div>
  </header>
}
