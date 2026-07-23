import { LogOut, Settings2 } from '../../../icons'


export function TopBar({ keyReady, mobilePanelOpen, onOpenSettings, session, onLogout }) {
  return <header className="topbar">
    <div className="topbar-heading">
      <button className="mobile-controls-button" type="button" onClick={onOpenSettings} aria-expanded={mobilePanelOpen} aria-controls="search-panel" aria-label="Ouvrir les paramètres de recherche"><Settings2 size={17} /><span>Paramètres</span></button>
      <div><p className="eyebrow">Google Places API (New)</p><h1>Recherche d’établissements</h1></div>
    </div>
    <div className="topbar-actions">
      <div className={`api-status ${keyReady ? 'ready' : ''}`} title={keyReady ? 'API configurée' : 'Clé API absente'}><span />{keyReady === null ? 'Vérification…' : keyReady ? 'API configurée' : 'Clé API absente'}</div>
      {session && onLogout && <div className="session-controls"><span>{session.user.display_name}</span><button type="button" onClick={onLogout} aria-label="Se déconnecter"><LogOut size={16} /></button></div>}
    </div>
  </header>
}
