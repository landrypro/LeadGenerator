import { useCallback, useEffect, useState } from 'react'

import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { complianceApi } from '../compliance/api/complianceApi'
import { exportApi } from './api/exportApi'

const DATASETS = ['prospects', 'contacts', 'contact_channels', 'activities', 'tasks', 'opportunities']
const COPY = {
  'fr-CA': {
    title: 'Exports CSV', intro: 'Les fichiers contiennent des données sensibles. Ils restent disponibles pendant 24 heures dans un espace privé.',
    dataset: 'Jeu de données', scope: 'Portée', self: 'Mes données', organization: 'Organisation',
    from: 'Date de début', to: 'Date de fin', create: 'Préparer le CSV', list: 'Mes demandes',
    refresh: 'Actualiser', download: 'Télécharger', more: 'Voir plus', empty: 'Aucune demande.',
    rows: 'lignes', omitted: 'champs ou lignes omis', expires: 'Expire le', status: 'État',
    sourceNotice: 'Les données de source externe sans droit d’export explicite sont omises.',
    queued: 'En attente', running: 'Préparation', ready: 'Prêt', failed: 'Échec', cancelled: 'Annulé', expired: 'Expiré',
    error: 'Impossible de charger les exports.',
    rules: 'Droits d’export des sources', source: 'Source', category: 'Catégorie', fields: 'Champs autorisés (codes séparés par des virgules)', purpose: 'Finalité', proof: 'Référence de preuve', allow: 'Autoriser', revoke: 'Révoquer', noRules: 'Aucune règle explicite.',
  },
  'en-CA': {
    title: 'CSV exports', intro: 'Files contain sensitive data. They remain available for 24 hours in private storage.',
    dataset: 'Dataset', scope: 'Scope', self: 'My data', organization: 'Organization',
    from: 'Start date', to: 'End date', create: 'Prepare CSV', list: 'My requests',
    refresh: 'Refresh', download: 'Download', more: 'Show more', empty: 'No requests yet.',
    rows: 'rows', omitted: 'fields or rows omitted', expires: 'Expires on', status: 'Status',
    sourceNotice: 'External source data without explicit export rights is omitted.',
    queued: 'Queued', running: 'Preparing', ready: 'Ready', failed: 'Failed', cancelled: 'Cancelled', expired: 'Expired',
    error: 'Could not load exports.',
    rules: 'Source export rights', source: 'Source', category: 'Category', fields: 'Allowed fields (comma-separated codes)', purpose: 'Purpose', proof: 'Evidence reference', allow: 'Allow', revoke: 'Revoke', noRules: 'No explicit rules.',
  },
}
const DATE_PREFIX = { prospects: 'created', contacts: 'created', contact_channels: 'obtained', activities: 'occurred', tasks: 'due', opportunities: 'expected_close' }

export function ExportsPage({ session }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = COPY[locale]
  const canOrganization = session.capabilities.includes('exports:create:organization')
  const canManageRules = session.capabilities.includes('exports:rules:manage')
  const [dataset, setDataset] = useState('prospects')
  const [scope, setScope] = useState('self')
  const [items, setItems] = useState([])
  const [cursor, setCursor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [rules, setRules] = useState([])
  const [sources, setSources] = useState([])
  const load = useCallback(async (next = '') => {
    try {
      const page = await exportApi.list(next)
      setItems((current) => next ? [...current, ...page.items] : page.items)
      setCursor(page.next_cursor)
      setError('')
    } catch (cause) { setError(toUserMessage(cause, copy.error)) }
    finally { setLoading(false) }
  }, [copy.error])
  useEffect(() => { load() }, [load])
  const loadRules = useCallback(async () => {
    if (!canManageRules) return
    try {
      const [ruleRows, acquisitions, providers] = await Promise.all([
        exportApi.listRules(), complianceApi.listAcquisitions(), complianceApi.listProviders(),
      ])
      setRules(ruleRows)
      setSources([
        ...(acquisitions.items ?? []).filter((item) => item.status === 'approved').map((item) => ({ value: `acquisition:${item.id}`, label: item.source_label ?? item.id })),
        ...(providers.items ?? []).filter((item) => item.status === 'active').map((item) => ({ value: `provider:${item.id}`, label: item.display_name ?? item.name ?? item.id })),
      ])
    } catch (cause) { setError(toUserMessage(cause, copy.error)) }
  }, [canManageRules, copy.error])
  useEffect(() => { loadRules() }, [loadRules])

  async function create(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const prefix = DATE_PREFIX[dataset]
    const filters = {}
    if (form.get('from')) filters[`${prefix}_from`] = form.get('from')
    if (form.get('to')) filters[`${prefix}_to`] = form.get('to')
    setBusy(true)
    try {
      await exportApi.create({ dataset, scope, filters }, globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`)
      await load()
      setMessage(locale === 'fr-CA' ? 'Demande créée.' : 'Request created.')
    } catch (cause) { setError(toUserMessage(cause)) }
    finally { setBusy(false) }
  }
  async function download(item) {
    setBusy(true)
    try {
      const blob = await exportApi.download(item.id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `marketteo-${item.dataset}-${item.id}.csv`
      anchor.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (cause) { setError(toUserMessage(cause)) }
    finally { setBusy(false) }
  }
  async function createRule(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = new FormData(formElement)
    const [target, id] = String(form.get('source')).split(':')
    const fields = String(form.get('fields')).split(',').map((field) => field.trim()).filter(Boolean)
    setBusy(true)
    try {
      await exportApi.createRule({
        acquisition_id: target === 'acquisition' ? id : null, provider_id: target === 'provider' ? id : null,
        data_category: form.get('category'), field_codes: fields, purpose: form.get('purpose'),
        status: 'allowed', valid_from: new Date().toISOString(), evidence_ref: String(form.get('proof')).trim(),
      })
      formElement.reset()
      await loadRules()
      setMessage(locale === 'fr-CA' ? 'Règle enregistrée.' : 'Rule saved.')
    } catch (cause) { setError(toUserMessage(cause)) }
    finally { setBusy(false) }
  }
  async function revokeRule(rule) {
    setBusy(true)
    try {
      await exportApi.updateRule(rule.id, {
        acquisition_id: rule.acquisition_id, provider_id: rule.provider_id,
        data_category: rule.data_category, field_codes: rule.field_codes, purpose: rule.purpose,
        status: 'denied', valid_from: new Date().toISOString(), evidence_ref: rule.evidence_ref,
        expected_version: rule.version,
      })
      await loadRules()
      await load()
    } catch (cause) { setError(toUserMessage(cause)) }
    finally { setBusy(false) }
  }
  const date = (value) => value ? new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
  return <main className="administration-page" aria-labelledby="exports-title">
    <header className="administration-page-heading"><h1 id="exports-title">{copy.title}</h1><p>{copy.intro}</p></header>
    {error && <ErrorBanner>{error}</ErrorBanner>}{message && <p role="status">{message}</p>}
    <section className="administration-card compliance-form-card"><h2>{copy.create}</h2>
      <p className="form-help">{copy.sourceNotice}</p>
      <form className="compliance-form" onSubmit={create}>
        <label>{copy.dataset}<select value={dataset} onChange={(event) => setDataset(event.target.value)}>{DATASETS.map((code) => <option key={code} value={code}>{code}</option>)}</select></label>
        <label>{copy.scope}<select value={scope} onChange={(event) => setScope(event.target.value)}><option value="self">{copy.self}</option>{canOrganization && <option value="organization">{copy.organization}</option>}</select></label>
        <label>{copy.from}<input type="date" name="from" /></label><label>{copy.to}<input type="date" name="to" /> </label>
        <button className="primary-button" disabled={busy}>{copy.create}</button>
      </form>
    </section>
    <section className="administration-card"><h2>{copy.list}</h2><button type="button" className="secondary-button" onClick={() => load()} disabled={busy}>{copy.refresh}</button>
      {loading ? <p role="status">{locale === 'fr-CA' ? 'Chargement…' : 'Loading…'}</p> : items.length === 0 ? <p>{copy.empty}</p> : <ul className="compliance-list">
        {items.map((item) => <li key={item.id}><div><strong>{item.dataset}</strong><small>{date(item.created_at)} · {item.scope === 'self' ? copy.self : copy.organization}</small><span className={`resource-status ${item.status}`}>{copy[item.status] ?? item.status}</span></div>
          <div><small>{item.row_count ?? '—'} {copy.rows} · {item.omitted_count ?? '—'} {copy.omitted}</small>{item.expires_at && <small>{copy.expires}: {date(item.expires_at)}</small>}{item.error_code && <small>{item.error_code}</small>}</div>
          {item.status === 'ready' && <button type="button" className="secondary-button" disabled={busy} onClick={() => download(item)}>{copy.download}</button>}
        </li>)}
      </ul>}{cursor && <button type="button" className="secondary-button" onClick={() => load(cursor)}>{copy.more}</button>}
    </section>
    {canManageRules && <section className="administration-card compliance-form-card"><h2>{copy.rules}</h2>
      <p className="form-help">{copy.sourceNotice}</p>
      <form className="compliance-form" onSubmit={createRule}>
        <label>{copy.source}<select name="source" required><option value="">—</option>{sources.map((source) => <option key={source.value} value={source.value}>{source.label}</option>)}</select></label>
        <label>{copy.category}<select name="category"><option value="prospect_profile">prospect_profile</option><option value="person_identity">person_identity</option><option value="channel">channel</option></select></label>
        <label>{copy.fields}<input name="fields" required maxLength="400" /></label>
        <label>{copy.purpose}<select name="purpose"><option value="commercial_follow_up">commercial_follow_up</option><option value="customer_relationship">customer_relationship</option><option value="supplier_relationship">supplier_relationship</option></select></label>
        <label>{copy.proof}<input name="proof" required maxLength="256" /></label>
        <button className="primary-button" disabled={busy}>{copy.allow}</button>
      </form>
      {rules.length ? <ul className="compliance-list">{rules.map((rule) => <li key={rule.id}><div><strong>{rule.data_category}</strong><small>{rule.purpose} · {rule.field_codes.join(', ')} · {rule.status}</small><small>{rule.evidence_ref}</small></div>{rule.status === 'allowed' && <button type="button" className="secondary-button" disabled={busy} onClick={() => revokeRule(rule)}>{copy.revoke}</button>}</li>)}</ul> : <p>{copy.noRules}</p>}
    </section>}
  </main>
}
