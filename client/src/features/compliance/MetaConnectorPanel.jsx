import { useCallback, useEffect, useState } from 'react'

import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { connectorApi } from './api/connectorApi'

const COPY = {
  'fr-CA': {
    title: 'Pilote Meta Lead Ads', intro: 'Le pilote reste fermé tant que le contrat et le binding ne sont pas approuvés. Aucun secret ni identifiant Meta brut n’est affiché.',
    loading: 'Chargement…', none: 'Aucun connecteur Meta déclaré.', create: 'Créer un brouillon', provider: 'Fournisseur Facebook actif', acquisition: 'Acquisition Facebook approuvée', form: 'Identifiant du formulaire Meta', evidence: 'Référence de preuve', permissions: 'Champs explicitement autorisés', name: 'Nom complet', email: 'Courriel', phone: 'Téléphone',
    submit: 'Soumettre à la revue', review: 'Approuver', disable: 'Arrêt d’urgence', expiry: 'Validité de la revue', status: 'État', reviewed: 'Une autre personne disposant de la capacité de revue doit approuver ce brouillon.', error: 'Impossible de gérer le connecteur Meta.',
  },
  'en-CA': {
    title: 'Meta Lead Ads pilot', intro: 'The pilot remains closed until its contract and binding have been approved. No secret or raw Meta identifier is displayed.',
    loading: 'Loading…', none: 'No Meta connector has been declared.', create: 'Create draft', provider: 'Active Facebook provider', acquisition: 'Approved Facebook acquisition', form: 'Meta form identifier', evidence: 'Evidence reference', permissions: 'Explicitly approved fields', name: 'Full name', email: 'Email', phone: 'Phone',
    submit: 'Submit for review', review: 'Approve', disable: 'Emergency stop', expiry: 'Review expiry', status: 'Status', reviewed: 'A different person with review capability must approve this draft.', error: 'Unable to manage the Meta connector.',
  },
}

export function MetaConnectorPanel({ session, providers, acquisitions }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = COPY[locale]
  const canManage = session.capabilities.includes('providers:manage')
  const canReview = session.capabilities.includes('providers:review')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const load = useCallback(async () => {
    setLoading(true)
    try { const page = await connectorApi.list(); setItems(page.items ?? []); setError('') } catch (cause) { setError(toUserMessage(cause, copy.error)) } finally { setLoading(false) }
  }, [copy.error])
  useEffect(() => { load() }, [load])
  const eligibleProviders = providers.filter((item) => item.status === 'active' && item.source_kind === 'facebook')
  const eligibleAcquisitions = acquisitions.filter((item) => item.status === 'approved' && item.source_kind === 'facebook')

  async function create(event) {
    event.preventDefault(); const form = new FormData(event.currentTarget)
    const requested_permissions = form.getAll('permission').map(String)
    try {
      await connectorApi.create({ provider_id: form.get('provider_id'), acquisition_id: form.get('acquisition_id'), form_id: String(form.get('form_id')).trim(), evidence_ref: String(form.get('evidence_ref')).trim() || undefined, requested_permissions, allow_full_name: requested_permissions.includes('full_name'), allow_email: requested_permissions.includes('email'), allow_phone: requested_permissions.includes('phone'), email_permission_status: requested_permissions.includes('email') ? 'allowed' : 'unknown', phone_permission_status: requested_permissions.includes('phone') ? 'allowed' : 'unknown' })
      event.currentTarget.reset(); setNotice(copy.create); await load()
    } catch (cause) { setError(toUserMessage(cause, copy.error)) }
  }
  async function submit(item) { try { await connectorApi.submit(item.id, item.version); setNotice(copy.submit); await load() } catch (cause) { setError(toUserMessage(cause, copy.error)) } }
  async function review(item) { try { await connectorApi.review(item.id, { version: item.version, approve: true, approved_permissions: item.requested_permissions, review_valid_until: new Date(Date.now() + 30 * 86400000).toISOString() }); setNotice(copy.review); await load() } catch (cause) { setError(toUserMessage(cause, copy.error)) } }
  async function disable(item) { try { await connectorApi.disable(item.id, item.binding_id); setNotice(copy.disable); await load() } catch (cause) { setError(toUserMessage(cause, copy.error)) } }

  return <section className="meta-connector-panel" aria-labelledby="meta-connector-title">
    <h2 id="meta-connector-title">{copy.title}</h2><p className="form-help">{copy.intro}</p>
    {error && <ErrorBanner><span>{error}</span></ErrorBanner>}{notice && <p className="success-banner" role="status">{notice}</p>}
    {canManage && <form className="compliance-form" onSubmit={create}>
      <label>{copy.provider}<select name="provider_id" required><option value="" />{eligibleProviders.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
      <label>{copy.acquisition}<select name="acquisition_id" required><option value="" />{eligibleAcquisitions.map((item) => <option key={item.id} value={item.id}>{item.source_label}</option>)}</select></label>
      <label>{copy.form}<input name="form_id" maxLength="128" required /></label><label>{copy.evidence}<input name="evidence_ref" maxLength="256" /></label>
      <fieldset className="full"><legend>{copy.permissions}</legend><label><input type="checkbox" name="permission" value="full_name" defaultChecked /> {copy.name}</label><label><input type="checkbox" name="permission" value="email" /> {copy.email}</label><label><input type="checkbox" name="permission" value="phone" /> {copy.phone}</label></fieldset>
      <button className="primary-button" type="submit">{copy.create}</button>
    </form>}
    {loading ? <p role="status">{copy.loading}</p> : <ul className="compliance-list">{items.map((item) => <li key={item.id}><div><strong>Meta Lead Ads</strong><small>{copy.status}: {item.status}</small><span className={`resource-status ${item.status}`}>{item.status}</span></div><div><small>{item.review_valid_until ? `${copy.expiry}: ${String(item.review_valid_until).slice(0, 10)}` : copy.reviewed}</small></div><div className="resource-actions">{canManage && item.status === 'draft' && <button type="button" className="secondary-button" onClick={() => submit(item)}>{copy.submit}</button>}{canReview && item.status === 'pending_review' && <button type="button" className="primary-button" onClick={() => review(item)}>{copy.review}</button>}{canManage && item.binding_status === 'active' && <button type="button" className="danger-link" onClick={() => disable(item)}>{copy.disable}</button>}</div></li>)}</ul>}
    {!loading && !items.length && <p className="form-help">{copy.none}</p>}
  </section>
}
