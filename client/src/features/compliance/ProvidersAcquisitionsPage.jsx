import { useCallback, useEffect, useMemo, useState } from 'react'

import { Check, Globe2, LoaderCircle } from '../../icons'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { ConfirmationDialog } from '../organizations/components/ConfirmationDialog'
import { complianceApi } from './api/complianceApi'


const SOURCE_KINDS = [['csv', 'CSV'], ['facebook', 'Facebook'], ['linkedin', 'LinkedIn'], ['open_data', 'Données ouvertes'], ['api', 'API'], ['other', 'Autre']]
const PURPOSES = [['commercial_follow_up', 'Suivi commercial'], ['customer_relationship', 'Relation client'], ['supplier_relationship', 'Relation fournisseur']]
const CATEGORIES = [['business_identity', 'Identité de l’établissement'], ['person_identity', 'Identité de personne'], ['email', 'Courriel'], ['phone', 'Téléphone'], ['social_profile', 'Profil social']]
const PROVIDER_STATUS = { draft: 'Brouillon — non utilisable', active: 'Actif', suspended: 'Suspendu — non utilisable', retired: 'Retiré — non utilisable' }
const ACQUISITION_STATUS = { pending_review: 'En attente de revue', approved: 'Approuvée', quarantined: 'En quarantaine', rejected: 'Rejetée' }

function isoDate(value) { return value ? String(value).slice(0, 10) : '' }
export function ProvidersAcquisitionsPage({ session }) {
  const [tab, setTab] = useState('providers')
  const [providers, setProviders] = useState([])
  const [acquisitions, setAcquisitions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [selectedProvider, setSelectedProvider] = useState(null)
  const [decision, setDecision] = useState(null)
  const canManageProviders = session.capabilities.includes('providers:manage')
  const canDeclare = session.capabilities.includes('acquisitions:declare')
  const canReview = session.capabilities.includes('acquisitions:review')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [providerPage, acquisitionPage] = await Promise.all([complianceApi.listProviders(), complianceApi.listAcquisitions()])
      setProviders(providerPage.items ?? []); setAcquisitions(acquisitionPage.items ?? [])
    } catch (requestError) { setError(toUserMessage(requestError, 'Impossible de charger la conformité.')) } finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])
  const activeProviders = useMemo(() => providers.filter((provider) => provider.status === 'active'), [providers])

  async function createProvider(event) {
    event.preventDefault(); const formElement = event.currentTarget; const form = new FormData(formElement)
    try { const created = await complianceApi.createProvider({ source_kind: form.get('source_kind'), label: String(form.get('label')).trim() }); setProviders((items) => [created, ...items]); formElement.reset(); setSuccess('Fournisseur créé en brouillon. Complétez son attestation avant toute utilisation.') } catch (requestError) { setError(toUserMessage(requestError, 'Impossible de créer le fournisseur.')) }
  }
  async function saveProvider(event) {
    event.preventDefault(); if (!selectedProvider) return; const form = new FormData(event.currentTarget)
    const values = (name) => form.getAll(name).map(String)
    const territories = String(form.get('territories')).split(',').map((item) => item.trim()).filter(Boolean)
    const purposes = values('purpose')
    const categories = values('category')
    try {
      const updated = await complianceApi.updateProvider(selectedProvider.id, {
        version: selectedProvider.version, label: String(form.get('label')).trim(), status: form.get('status'), terms_reference: String(form.get('terms_reference')).trim() || undefined, terms_url: String(form.get('terms_url')).trim() || undefined, valid_from: form.get('valid_from') ? new Date(`${form.get('valid_from')}T00:00:00Z`).toISOString() : undefined, valid_until: form.get('valid_until') ? new Date(`${form.get('valid_until')}T23:59:59Z`).toISOString() : undefined,
        ...(territories.length ? { allowed_territories: territories } : {}),
        ...(purposes.length ? { allowed_purposes: purposes } : {}),
        ...(categories.length ? { allowed_data_categories: categories } : {}),
        rights_attested: form.get('rights_attested') === 'on',
      })
      setProviders((items) => items.map((item) => item.id === updated.id ? updated : item)); setSelectedProvider(updated); setSuccess('Fournisseur enregistré.')
    } catch (requestError) { setError(toUserMessage(requestError, 'Impossible de modifier le fournisseur.')) }
  }
  async function declareAcquisition(event) {
    event.preventDefault(); const formElement = event.currentTarget; const form = new FormData(formElement); const categories = form.getAll('category').map(String)
    try { const created = await complianceApi.declareAcquisition({ source_kind: form.get('source_kind'), source_label: String(form.get('source_label')).trim(), provider_id: form.get('provider_id'), purpose: form.get('purpose'), territory: String(form.get('territory')).trim(), obtained_at: new Date(`${form.get('obtained_at')}T12:00:00Z`).toISOString(), data_categories: categories, external_reference: String(form.get('external_reference')).trim() || undefined }); setAcquisitions((items) => [created, ...items]); formElement.reset(); setSuccess(created.status === 'approved' ? 'Acquisition déclarée et approuvée selon les règles du fournisseur.' : 'Acquisition déclarée ; elle requiert une revue ou reste en quarantaine.') } catch (requestError) { setError(toUserMessage(requestError, 'Impossible de déclarer l’acquisition.')) }
  }
  async function confirmDecision() {
    if (!decision) return
    try { const updated = await complianceApi.decideAcquisition(decision.item.id, { version: decision.item.version, decision: decision.action, reason_code: decision.action === 'reject' ? 'manual_review_rejected' : undefined }); setAcquisitions((items) => items.map((item) => item.id === updated.id ? updated : item)); setSuccess(decision.action === 'approve' ? 'Acquisition approuvée. Cette approbation ne vaut pas permission de contact.' : 'Acquisition rejetée.'); setDecision(null) } catch (requestError) { setError(toUserMessage(requestError, 'Impossible d’enregistrer la décision.')); setDecision(null) }
  }

  return <main className="administration-page compliance-page" aria-labelledby="compliance-title">
    <header className="administration-page-heading"><p className="eyebrow">Conformité des sources</p><h1 id="compliance-title">Fournisseurs et acquisitions</h1><p>Documentez l’origine avant toute création de données CRM. Une acquisition approuvée ne vaut jamais permission de contact.</p></header>
    {error && <ErrorBanner><span>{error}</span></ErrorBanner>}{success && <div className="success-banner" role="status"><Check size={18} /><span>{success}</span></div>}
    <div className="administration-tabs" role="tablist" aria-label="Conformité"><button type="button" role="tab" aria-selected={tab === 'providers'} onClick={() => setTab('providers')}>Fournisseurs</button><button type="button" role="tab" aria-selected={tab === 'acquisitions'} onClick={() => setTab('acquisitions')}>Acquisitions</button></div>
    {loading ? <div className="administration-loading" aria-live="polite"><LoaderCircle className="spin" size={20} /> Chargement…</div> : tab === 'providers' ? <>
      {canManageProviders && <section className="administration-card compliance-form-card"><h2>Nouveau fournisseur</h2><form className="compliance-form compact-form" onSubmit={createProvider}><label>Type de source<select name="source_kind" defaultValue="csv">{SOURCE_KINDS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Nom du fournisseur<input name="label" maxLength="160" required /></label><button className="primary-button" type="submit">Créer le brouillon</button></form></section>}
      <section className="administration-card"><h2>Fournisseurs enregistrés</h2><ul className="compliance-list">{providers.map((provider) => <li key={provider.id}><div><strong>{provider.label}</strong><small>{SOURCE_KINDS.find(([value]) => value === provider.source_kind)?.[1] ?? provider.source_kind}</small><span className={`resource-status ${provider.status}`}>{PROVIDER_STATUS[provider.status] ?? provider.status}</span></div><div>{provider.valid_until && <small>Valide jusqu’au {isoDate(provider.valid_until)}</small>}{provider.terms_url && <a href={provider.terms_url} target="_blank" rel="noopener noreferrer"><Globe2 size={14} /> Conditions</a>}</div>{canManageProviders && <button className="secondary-button" type="button" onClick={() => setSelectedProvider(provider)}>Modifier</button>}</li>)}</ul>{!providers.length && <p className="form-help">Aucun fournisseur déclaré.</p>}</section>
      {selectedProvider && <section className="administration-card compliance-form-card"><h2>Modifier {selectedProvider.label}</h2><form className="compliance-form" onSubmit={saveProvider}><label>Nom<input name="label" defaultValue={selectedProvider.label} required /></label><label>État<select name="status" defaultValue={selectedProvider.status}>{Object.entries(PROVIDER_STATUS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Référence contractuelle<input name="terms_reference" defaultValue={selectedProvider.terms_reference ?? ''} /></label><label>URL des conditions<input name="terms_url" type="url" defaultValue={selectedProvider.terms_url ?? ''} /></label><label>Valide à partir du<input name="valid_from" type="date" defaultValue={isoDate(selectedProvider.valid_from)} /></label><label>Valide jusqu’au<input name="valid_until" type="date" defaultValue={isoDate(selectedProvider.valid_until)} /></label><label className="full">Territoires (séparés par virgules)<input name="territories" defaultValue={(selectedProvider.allowed_territories ?? []).join(', ')} placeholder="CA-QC, CA-ON" /></label><fieldset className="full"><legend>Finalités autorisées</legend>{PURPOSES.map(([value,label]) => <label key={value}><input type="checkbox" name="purpose" value={value} defaultChecked={selectedProvider.allowed_purposes?.includes(value)} /> {label}</label>)}</fieldset><fieldset className="full"><legend>Catégories autorisées</legend>{CATEGORIES.map(([value,label]) => <label key={value}><input type="checkbox" name="category" value={value} defaultChecked={selectedProvider.allowed_data_categories?.includes(value)} /> {label}</label>)}</fieldset><label className="full"><input name="rights_attested" type="checkbox" defaultChecked={Boolean(selectedProvider.rights_attested_at)} /> J’atteste disposer des droits nécessaires pour cette source.</label><div className="form-actions"><button className="secondary-button" type="button" onClick={() => setSelectedProvider(null)}>Fermer</button><button className="primary-button" type="submit">Enregistrer</button></div></form></section>}
    </> : <>
      {canDeclare && <section className="administration-card compliance-form-card"><h2>Déclarer une acquisition</h2>{activeProviders.length ? <form className="compliance-form" onSubmit={declareAcquisition}><label>Fournisseur<select name="provider_id" required>{activeProviders.map((provider) => <option key={provider.id} value={provider.id}>{provider.label}</option>)}</select></label><label>Type<select name="source_kind" defaultValue={activeProviders[0].source_kind}>{SOURCE_KINDS.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Libellé de la source<input name="source_label" required maxLength="160" /></label><label>Territoire<input name="territory" defaultValue="CA-QC" required maxLength="16" /></label><label>Finalité<select name="purpose" defaultValue="commercial_follow_up">{PURPOSES.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Date d’obtention<input name="obtained_at" type="date" required /></label><label className="full">Référence externe (facultatif)<input name="external_reference" maxLength="128" /></label><fieldset className="full"><legend>Catégories déclarées</legend>{CATEGORIES.map(([value,label], index) => <label key={value}><input type="checkbox" name="category" value={value} defaultChecked={index === 0} /> {label}</label>)}</fieldset><button className="primary-button" type="submit">Déclarer l’acquisition</button></form> : <p className="form-help">Activez et attestez un fournisseur compatible avant de déclarer une acquisition.</p>}</section>}
      <section className="administration-card"><h2>Historique des acquisitions</h2><p className="form-help">L’approbation de provenance ne crée aucune permission de contact.</p><ul className="compliance-list">{acquisitions.map((item) => <li key={item.id}><div><strong>{item.source_label}</strong><small>{item.territory} · {isoDate(item.obtained_at)}</small><span className={`resource-status ${item.status}`}>{ACQUISITION_STATUS[item.status] ?? item.status}</span></div><div><small>{item.data_categories.join(', ')}</small>{item.decision_reason_code && <small>Motif : {item.decision_reason_code}</small>}</div>{canReview && ['pending_review', 'quarantined'].includes(item.status) && <div className="resource-actions"><button className="secondary-button" type="button" onClick={() => setDecision({ item, action: 'approve' })}>Approuver</button><button className="danger-link" type="button" onClick={() => setDecision({ item, action: 'reject' })}>Rejeter</button></div>}</li>)}</ul>{!acquisitions.length && <p className="form-help">Aucune acquisition déclarée.</p>}</section>
    </>}
    {decision && <ConfirmationDialog title={decision.action === 'approve' ? 'Approuver cette acquisition ?' : 'Rejeter cette acquisition ?'} confirmLabel={decision.action === 'approve' ? 'Approuver' : 'Rejeter'} onCancel={() => setDecision(null)} onConfirm={confirmDecision}><p>{decision.action === 'approve' ? 'La provenance deviendra utilisable, sans autoriser automatiquement le contact.' : 'La déclaration restera auditée mais ne pourra pas servir de provenance.'}</p></ConfirmationDialog>}
  </main>
}
