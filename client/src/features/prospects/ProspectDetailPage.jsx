import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Building2, Check, LoaderCircle, UsersRound } from '../../icons'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { prospectApi } from './api/prospectApi'

const MANUAL_SOURCE = { kind: 'manual', purpose: 'commercial_follow_up', territory: 'CA-QC' }

function permissionLabel(status) {
  return { unknown: 'Permission non déterminée', allowed: 'Contact autorisé', do_not_contact: 'Ne pas contacter', opted_out: 'Opposition enregistrée' }[status] ?? status
}

export function ProspectDetailPage({ routeParams, session }) {
  const prospectId = routeParams?.prospectId
  const [prospect, setProspect] = useState(null)
  const [contacts, setContacts] = useState([])
  const [channels, setChannels] = useState([])
  const [contactChannels, setContactChannels] = useState({})
  const [permissions, setPermissions] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [contactName, setContactName] = useState('')
  const [channelValue, setChannelValue] = useState('')
  const [channelType, setChannelType] = useState('email')
  const [channelTarget, setChannelTarget] = useState('prospect')
  const controllerRef = useRef(null)
  const canUpdate = session.capabilities.includes('prospects:update')
  const canWriteContacts = session.capabilities.includes('contacts:write')

  const load = useCallback(async () => {
    if (!prospectId) return
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setLoading(true)
    setError('')
    try {
      const [nextProspect, contactsPage, nextChannels] = await Promise.all([
        prospectApi.get(prospectId, controller.signal),
        prospectApi.listContacts(prospectId, controller.signal),
        prospectApi.listChannels(prospectId, controller.signal),
      ])
      const nextContactChannels = Object.fromEntries(await Promise.all((contactsPage.items ?? []).map(async (contact) => [
        contact.id,
        await prospectApi.listContactChannels(contact.id, controller.signal),
      ])))
      const allChannels = [...(nextChannels ?? []), ...Object.values(nextContactChannels).flat()]
      const permissionPairs = await Promise.all(allChannels.map(async (channel) => [channel.id, await prospectApi.getPermission(channel.id, controller.signal)]))
      setProspect(nextProspect)
      setContacts(contactsPage.items ?? [])
      setChannels(nextChannels ?? [])
      setContactChannels(nextContactChannels)
      setPermissions(Object.fromEntries(permissionPairs))
    } catch (requestError) {
      if (requestError?.name !== 'AbortError') setError(toUserMessage(requestError, 'Impossible de charger le prospect.'))
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null
      setLoading(false)
    }
  }, [prospectId])

  useEffect(() => { load(); return () => controllerRef.current?.abort() }, [load])

  const profilePayload = useMemo(() => prospect ? ({
    version: prospect.version,
    internal_alias: prospect.internal_alias,
    industry_label: prospect.industry_label || undefined,
    city: prospect.city || undefined,
    priority: prospect.priority,
    tags: prospect.tags,
    purpose: 'commercial_follow_up', territory: 'CA-QC',
  }) : null, [prospect])

  async function saveProfile(event) {
    event.preventDefault()
    if (!prospect || !profilePayload) return
    const form = new FormData(event.currentTarget)
    try {
      const updated = await prospectApi.update(prospect.id, {
        ...profilePayload,
        internal_alias: String(form.get('internal_alias') || '').trim(),
        industry_label: String(form.get('industry_label') || '').trim() || undefined,
        city: String(form.get('city') || '').trim() || undefined,
        priority: Number(form.get('priority') || 0),
        tags: String(form.get('tags') || '').split(',').map((value) => value.trim()).filter(Boolean),
      })
      setProspect(updated); setSuccess('Le profil CRM a été enregistré.'); setError('')
    } catch (requestError) { setError(toUserMessage(requestError, 'Impossible de modifier le profil.')) }
  }

  async function addContact(event) {
    event.preventDefault()
    if (!contactName.trim()) return
    try { await prospectApi.createContact(prospectId, { display_name: contactName.trim(), source: MANUAL_SOURCE }); setContactName(''); setSuccess('Le contact a été ajouté.'); await load() } catch (requestError) { setError(toUserMessage(requestError, 'Impossible d’ajouter le contact.')) }
  }

  async function addChannel(event) {
    event.preventDefault()
    if (!channelValue.trim()) return
    try {
      await prospectApi.createChannel({
        channel_type: channelType,
        value: channelValue.trim(),
        ...(channelTarget === 'prospect' ? { prospect_id: prospectId } : { contact_id: channelTarget }),
        source: MANUAL_SOURCE,
      })
      setChannelValue(''); setSuccess('Le canal a été ajouté avec une permission non déterminée.'); await load()
    } catch (requestError) { setError(toUserMessage(requestError, 'Impossible d’ajouter le canal.')) }
  }

  async function changePermission(channel, status) {
    const permission = permissions[channel.id]
    if (!permission) return
    try {
      const updated = await prospectApi.updatePermission(channel.id, {
        version: permission.version,
        status,
        reason: status === 'allowed' ? undefined : 'Décision manuelle',
        legal_basis_code: status === 'allowed' ? 'legitimate_interest' : undefined,
        provenance_id: status === 'allowed' ? channel.provenance_id : undefined,
      })
      setPermissions((current) => ({ ...current, [channel.id]: updated })); setSuccess('La permission a été mise à jour.')
    } catch (requestError) { setError(toUserMessage(requestError, 'Impossible de modifier la permission.')) }
  }

  if (loading && !prospect) return <main className="administration-page"><div className="administration-loading"><LoaderCircle className="spin" size={20} /> Chargement du prospect…</div></main>
  if (!prospect) return <main className="administration-page"><section className="route-status-card"><h1>Prospect indisponible</h1><p>{error || 'Ce prospect est introuvable.'}</p><button type="button" className="secondary-button" onClick={load}>Réessayer</button></section></main>

  return <main className="administration-page prospect-detail-page" aria-labelledby="prospect-detail-title">
    <header className="administration-page-heading"><p className="eyebrow">Portefeuille CRM</p><h1 id="prospect-detail-title">{prospect.internal_alias}</h1><p>Profil CRM, contacts et permissions. Aucune donnée descriptive Google n’est copiée dans cette fiche.</p></header>
    {error && <ErrorBanner><span>{error}</span></ErrorBanner>}{success && <div className="success-banner" role="status"><Check size={18} />{success}</div>}
    <div className="prospect-detail-grid">
      <section className="administration-card"><div className="administration-card-icon"><Building2 size={21} /></div><h2>Profil CRM</h2>{canUpdate ? <form className="organization-form" onSubmit={saveProfile}>
        <label htmlFor="profile-alias">Nom interne</label><input id="profile-alias" name="internal_alias" defaultValue={prospect.internal_alias} required maxLength="160" />
        <label htmlFor="profile-industry">Secteur</label><input id="profile-industry" name="industry_label" defaultValue={prospect.industry_label || ''} maxLength="120" />
        <label htmlFor="profile-city">Ville CRM</label><input id="profile-city" name="city" defaultValue={prospect.city || ''} maxLength="120" />
        <label htmlFor="profile-priority">Priorité</label><select id="profile-priority" name="priority" defaultValue={String(prospect.priority)}>{[0,1,2,3,4,5].map((value) => <option key={value} value={value}>{value}/5</option>)}</select>
        <label htmlFor="profile-tags">Étiquettes</label><input id="profile-tags" name="tags" defaultValue={(prospect.tags ?? []).join(', ')} maxLength="320" /><p className="form-help">Séparez les étiquettes par des virgules.</p>
        <button className="primary-button" type="submit">Enregistrer le profil</button></form> : <p>Vous pouvez consulter ce profil, mais votre rôle ne permet pas de le modifier.</p>}</section>
      <section className="administration-card"><div className="administration-card-icon"><UsersRound size={21} /></div><h2>Contacts</h2>{contacts.length ? <ul className="prospect-contact-list">{contacts.map((contact) => <li key={contact.id}><strong>{contact.display_name}</strong>{contact.role_label && <span>{contact.role_label}</span>}{(contactChannels[contact.id] ?? []).map((channel) => <small key={channel.id}>{channel.channel_type} · {channel.value} · {permissionLabel(permissions[channel.id]?.status || 'unknown')}</small>)}</li>)}</ul> : <p className="form-help">Aucune personne de contact n’est enregistrée.</p>}{canWriteContacts && <form className="prospect-inline-form" onSubmit={addContact}><label htmlFor="contact-name">Ajouter une personne</label><input id="contact-name" value={contactName} onChange={(event) => setContactName(event.target.value)} maxLength="160" required /><button className="secondary-button" type="submit">Ajouter</button></form>}</section>
      <section className="administration-card prospect-channels-card"><h2>Canaux et permissions</h2>{channels.length ? <ul className="prospect-channel-list">{channels.map((channel) => { const permission = permissions[channel.id]; return <li key={channel.id}><div><strong>{channel.channel_type === 'email' ? 'Courriel' : channel.channel_type === 'phone' ? 'Téléphone' : channel.channel_type}</strong><span>{channel.value}</span><small>{permissionLabel(permission?.status || 'unknown')}</small></div>{permission && (session.capabilities.includes('permissions:allow') || session.capabilities.includes('permissions:restrict')) && <select aria-label={`Permission ${channel.value}`} value={permission.status} onChange={(event) => changePermission(channel, event.target.value)}><option value="unknown" disabled>Non déterminée</option>{session.capabilities.includes('permissions:allow') && <option value="allowed">Autorisé</option>}{session.capabilities.includes('permissions:restrict') && <><option value="do_not_contact">Ne pas contacter</option><option value="opted_out">Opposition</option></>}</select>}</li> })}</ul> : <p className="form-help">Aucun canal direct n’est enregistré.</p>}{canWriteContacts && <form className="prospect-inline-form" onSubmit={addChannel}><label htmlFor="channel-target">Associer le canal à</label><select id="channel-target" value={channelTarget} onChange={(event) => setChannelTarget(event.target.value)}><option value="prospect">L’établissement</option>{contacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.display_name}</option>)}</select><label htmlFor="channel-value">Ajouter un canal</label><div><select value={channelType} onChange={(event) => setChannelType(event.target.value)} aria-label="Type de canal"><option value="email">Courriel</option><option value="phone">Téléphone</option><option value="linkedin">LinkedIn</option><option value="facebook">Facebook</option><option value="other">Autre</option></select><input id="channel-value" value={channelValue} onChange={(event) => setChannelValue(event.target.value)} maxLength="512" required /><button className="secondary-button" type="submit">Ajouter</button></div></form>}</section>
    </div>
  </main>
}
