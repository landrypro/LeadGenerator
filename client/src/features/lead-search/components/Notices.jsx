import { AlertTriangle, Info, X } from '../../../icons'
import { ErrorBanner } from '../../../shared/ui/Feedback'
import { leadSearchMessages } from '../messages'


export function Notices({ copy = leadSearchMessages['fr-CA'], error, keyReady, onClearError }) {
  return <>
    {error && <ErrorBanner><AlertTriangle size={19} /><span>{error}</span><button onClick={onClearError} aria-label={copy.closeSettings}><X size={17} /></button></ErrorBanner>}
    {keyReady === false && <div className="setup-banner"><div className="setup-icon"><Info size={20} /></div><div><strong>{copy.setupTitle}</strong><p>{copy.setupText}</p></div></div>}
  </>
}
