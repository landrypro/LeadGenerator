import { Building2, Info, MapPin, Sparkles, X } from '../../../icons'
import { Field } from '../../../shared/ui/FormControls'


export function IdentityModal({ requester, setRequester, onClose, onConfirm }) {
  const updateRequester = (key, value) => setRequester((current) => ({ ...current, [key]: value }))

  return <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <section className="identity-dialog" role="dialog" aria-modal="true" aria-labelledby="identity-title">
      <div className="dialog-head"><div className="dialog-icon"><Building2 size={21} /></div><div><p className="eyebrow">Identification de la demande</p><h2 id="identity-title">Avant la recherche Google</h2></div><button type="button" onClick={onClose} aria-label="Fermer"><X size={18} /></button></div>
      <p className="dialog-intro">Indiquez qui effectue cette recherche. Une même adresse professionnelle ne peut lancer qu’une recherche à la fois.</p>
      <form onSubmit={onConfirm}>
        <div className="identity-grid">
          <Field label="Prénom"><input aria-label="Prénom" autoFocus autoComplete="given-name" value={requester.first_name} onChange={(event) => updateRequester('first_name', event.target.value)} placeholder="Votre prénom" minLength="1" maxLength="80" required /></Field>
          <Field label="Raison sociale"><input aria-label="Raison sociale" autoComplete="organization" value={requester.company_name} onChange={(event) => updateRequester('company_name', event.target.value)} placeholder="Nom de l’entreprise" minLength="2" maxLength="160" required /></Field>
        </div>
        <Field label="Adresse professionnelle">
          <div className="input-with-icon"><MapPin size={17} /><input aria-label="Adresse professionnelle" autoComplete="street-address" value={requester.business_address} onChange={(event) => updateRequester('business_address', event.target.value)} placeholder="Numéro, rue, ville et pays" minLength="5" maxLength="240" required /></div>
        </Field>
        <p className="privacy-note"><Info size={14} /> Ces informations sont utilisées pendant la recherche. Consultez notre <a href="/confidentialite.html" target="_blank" rel="noopener noreferrer">politique de confidentialité</a>.</p>
        <div className="dialog-actions"><button className="secondary-button" type="button" onClick={onClose}>Annuler</button><button className="primary-button" type="submit"><Sparkles size={17} /> Confirmer la recherche</button></div>
      </form>
    </section>
  </div>
}
