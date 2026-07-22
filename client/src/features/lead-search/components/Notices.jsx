import { AlertTriangle, Info, X } from '../../../icons'


export function Notices({ error, keyReady, onClearError }) {
  return <>
    {error && <div className="error-banner"><AlertTriangle size={19} /><span>{error}</span><button onClick={onClearError} aria-label="Fermer"><X size={17} /></button></div>}
    {keyReady === false && <div className="setup-banner"><div className="setup-icon"><Info size={20} /></div><div><strong>Une étape avant la première recherche</strong><p>Ajoutez <code>GOOGLE_MAPS_API_KEY</code> aux variables d’environnement du serveur, puis relancez l’API.</p></div></div>}
  </>
}
