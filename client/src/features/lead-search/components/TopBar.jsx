import { Settings2 } from '../../../icons'


export function TopBar({ keyReady, mobilePanelOpen, onOpenSettings }) {
  return <header className="topbar">
    <div className="topbar-heading">
      <button className="mobile-controls-button" type="button" onClick={onOpenSettings} aria-expanded={mobilePanelOpen} aria-controls="search-panel" aria-label="Ouvrir les paramètres de recherche"><Settings2 size={17} /><span>Paramètres</span></button>
      <div><p className="eyebrow">Google Places API (New)</p><h1>Générateur de leads locaux</h1></div>
    </div>
    <div className={`api-status ${keyReady ? 'ready' : ''}`} title={keyReady ? 'API configurée' : 'Clé API absente'}><span />{keyReady === null ? 'Vérification…' : keyReady ? 'API configurée' : 'Clé API absente'}</div>
  </header>
}
