import { useEffect, useMemo, useRef, useState } from 'react'

import { Building2, Check, LoaderCircle } from '../../icons'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { IANA_TIMEZONES } from '../../shared/ianaTimezones'
import { organizationApi } from './api/organizationApi'
import { useOrganization } from './hooks/useOrganization'


const ORGANIZATION_MESSAGES = Object.freeze({
  'fr-CA': Object.freeze({ administration: 'Administration', unavailable: 'Organisation indisponible', load: 'Chargement de l’organisation…', unavailableText: 'Impossible de charger l’organisation.', retry: 'Réessayer', title: 'Organisation', description: 'Consultez les informations de l’organisation active', descriptionEditable: ' et mettez-les à jour.', newer: 'Une version plus récente existe', currentVersion: 'Votre saisie est conservée. Version chargée : {version}. Version actuelle signalée : {conflictVersion}.', reload: 'Recharger la version actuelle', reloading: 'Rechargement…', summary: 'Informations actuelles', name: 'Nom', language: 'Langue', timezone: 'Fuseau horaire', status: 'État', created: 'Créée le', updated: 'Mise à jour le', edit: 'Modifier l’organisation', timezoneIana: 'Fuseau horaire IANA', timezoneHelp: 'Commencez à saisir un continent ou une ville pour afficher les fuseaux proposés.', save: 'Enregistrer les modifications', saving: 'Enregistrement…', saved: 'Les informations de l’organisation ont été enregistrées.', reloaded: 'La version actuelle a été chargée. Vérifiez vos modifications avant de les saisir à nouveau.', updateError: 'Impossible de modifier l’organisation.', statuses: Object.freeze({ active: 'Active', provisioning: 'En cours d’activation', suspended: 'Suspendue' }) }),
  'en-CA': Object.freeze({ administration: 'Administration', unavailable: 'Organization unavailable', load: 'Loading organization…', unavailableText: 'Unable to load the organization.', retry: 'Try again', title: 'Organization', description: 'View the active organization’s information', descriptionEditable: ' and update it.', newer: 'A newer version is available', currentVersion: 'Your entry was kept. Loaded version: {version}. Reported current version: {conflictVersion}.', reload: 'Reload current version', reloading: 'Reloading…', summary: 'Current information', name: 'Name', language: 'Language', timezone: 'Time zone', status: 'Status', created: 'Created', updated: 'Updated', edit: 'Edit organization', timezoneIana: 'IANA time zone', timezoneHelp: 'Start typing a continent or city to see suggested time zones.', save: 'Save changes', saving: 'Saving…', saved: 'Organization information was saved.', reloaded: 'The current version was loaded. Review your changes before entering them again.', updateError: 'Unable to update the organization.', statuses: Object.freeze({ active: 'Active', provisioning: 'Being activated', suspended: 'Suspended' }) }),
})

function formatDate(value, locale, timezone) {
  try {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: 'long',
      timeStyle: 'short',
      timeZone: timezone,
    }).format(new Date(value))
  } catch {
    return new Intl.DateTimeFormat('fr-CA', {
      dateStyle: 'long',
      timeStyle: 'short',
      timeZone: 'America/Toronto',
    }).format(new Date(value))
  }
}


export function OrganizationPage({ session, onOrganizationUpdated }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = ORGANIZATION_MESSAGES[locale]
  const { organization, setOrganization, loading, error: loadError, load } = useOrganization()
  const [draft, setDraft] = useState({ name: '', locale: 'fr-CA', timezone: 'America/Toronto' })
  const [submitting, setSubmitting] = useState(false)
  const [mutationError, setMutationError] = useState('')
  const [conflictVersion, setConflictVersion] = useState('')
  const [success, setSuccess] = useState('')
  const [timezoneSuggestionsVisible, setTimezoneSuggestionsVisible] = useState(false)
  const mutationControllerRef = useRef(null)
  const mutationSequenceRef = useRef(0)
  const canUpdate = session.capabilities.includes('organization:update')

  useEffect(() => {
    if (!organization) return
    setDraft({
      name: organization.name,
      locale: organization.locale,
      timezone: organization.timezone,
    })
    setConflictVersion('')
  }, [organization])

  useEffect(() => () => {
    mutationSequenceRef.current += 1
    mutationControllerRef.current?.abort()
  }, [])

  const changes = useMemo(() => {
    if (!organization) return {}
    const nextChanges = {}
    const normalizedName = draft.name.trim()
    if (normalizedName !== organization.name) nextChanges.name = normalizedName
    if (draft.locale !== organization.locale) nextChanges.locale = draft.locale
    if (draft.timezone.trim() !== organization.timezone) nextChanges.timezone = draft.timezone.trim()
    return nextChanges
  }, [draft, organization])
  const hasChanges = Object.keys(changes).length > 0

  function updateDraft(field, value) {
    setDraft((current) => ({ ...current, [field]: value }))
    setMutationError('')
    setConflictVersion('')
    setSuccess('')
  }

  async function submit(event) {
    event.preventDefault()
    if (!organization || !hasChanges || submitting || mutationControllerRef.current) return
    const controller = new AbortController()
    const sequence = mutationSequenceRef.current + 1
    mutationSequenceRef.current = sequence
    mutationControllerRef.current = controller
    setSubmitting(true)
    setMutationError('')
    setConflictVersion('')
    setSuccess('')
    try {
      const updated = await organizationApi.update({ version: organization.version, ...changes }, controller.signal)
      if (mutationSequenceRef.current !== sequence) return
      setOrganization(updated)
      onOrganizationUpdated?.(updated)
      setSuccess(copy.saved)
    } catch (updateError) {
      if (updateError?.name === 'AbortError' || mutationSequenceRef.current !== sequence) return
      if (updateError?.code === 'organization_version_conflict') {
        setConflictVersion(updateError.fields?.version ?? 'inconnue')
      } else {
        setMutationError(toUserMessage(updateError, copy.updateError))
      }
    } finally {
      if (mutationSequenceRef.current === sequence) {
        mutationControllerRef.current = null
        setSubmitting(false)
      }
    }
  }

  async function reloadAfterConflict() {
    const reloaded = await load()
    if (reloaded) {
      setMutationError('')
      setConflictVersion('')
      setSuccess(copy.reloaded)
    }
  }

  if (loading && !organization) {
    return <main className="administration-page organization-page" aria-live="polite">
      <div className="administration-loading"><LoaderCircle className="spin" size={20} /> {copy.load}</div>
    </main>
  }

  if (!organization) {
    return <main className="administration-page organization-page" aria-labelledby="organization-error-title">
      <section className="route-status-card">
        <p className="eyebrow">{copy.administration}</p>
        <h1 id="organization-error-title">{copy.unavailable}</h1>
        <p>{loadError || copy.unavailableText}</p>
        <button className="secondary-button" type="button" onClick={load}>{copy.retry}</button>
      </section>
    </main>
  }

  return <main className="administration-page organization-page" aria-labelledby="organization-title">
    <header className="administration-page-heading">
      <p className="eyebrow">{copy.administration}</p>
      <h1 id="organization-title">{copy.title}</h1>
      <p>{copy.description}{canUpdate ? copy.descriptionEditable : '.'}</p>
    </header>

    {loadError && <ErrorBanner><span>{loadError}</span></ErrorBanner>}
    {mutationError && <ErrorBanner><span>{mutationError}</span></ErrorBanner>}
    {success && <div className="success-banner" role="status"><Check size={18} /><span>{success}</span></div>}
    {conflictVersion && <section className="conflict-banner" role="alert" aria-labelledby="organization-conflict-title">
      <h2 id="organization-conflict-title">{copy.newer}</h2>
      <p>
        {copy.currentVersion.replace('{version}', organization.version).replace('{conflictVersion}', conflictVersion)}
      </p>
      <button className="secondary-button" type="button" onClick={reloadAfterConflict} disabled={loading}>
        {loading ? copy.reloading : copy.reload}
      </button>
    </section>}

    <div className="organization-grid">
      <section className="administration-card" aria-labelledby="organization-summary-title">
        <div className="administration-card-icon" aria-hidden="true"><Building2 size={22} /></div>
        <h2 id="organization-summary-title">{copy.summary}</h2>
        <dl className="account-details organization-details">
          <div><dt>{copy.name}</dt><dd>{organization.name}</dd></div>
          <div><dt>{copy.language}</dt><dd>{organization.locale === 'fr-CA' ? 'Français (Canada)' : 'English (Canada)'}</dd></div>
          <div><dt>{copy.timezone}</dt><dd>{organization.timezone}</dd></div>
          <div><dt>{copy.status}</dt><dd><span className={`organization-status ${organization.status}`}>{copy.statuses[organization.status] ?? organization.status}</span></dd></div>
          <div><dt>{copy.created}</dt><dd><time dateTime={organization.created_at}>{formatDate(organization.created_at, locale, organization.timezone)}</time></dd></div>
          <div><dt>{copy.updated}</dt><dd><time dateTime={organization.updated_at}>{formatDate(organization.updated_at, locale, organization.timezone)}</time></dd></div>
        </dl>
      </section>

      {canUpdate && <section className="administration-card" aria-labelledby="organization-edit-title">
        <h2 id="organization-edit-title">{copy.edit}</h2>
        <form className="organization-form" onSubmit={submit}>
          <label htmlFor="organization-name">{copy.name}</label>
          <input id="organization-name" value={draft.name} onChange={(event) => updateDraft('name', event.target.value)} minLength="1" maxLength="160" required />

          <label htmlFor="organization-locale">{copy.language}</label>
          <select id="organization-locale" value={draft.locale} onChange={(event) => updateDraft('locale', event.target.value)}>
            <option value="fr-CA">Français (Canada)</option>
            <option value="en-CA">English (Canada)</option>
          </select>

          <label htmlFor="organization-timezone">{copy.timezoneIana}</label>
          <input id="organization-timezone" list="organization-timezones" value={draft.timezone} onFocus={() => setTimezoneSuggestionsVisible(true)} onChange={(event) => updateDraft('timezone', event.target.value)} minLength="1" maxLength="64" required />
          <datalist id="organization-timezones">
            {timezoneSuggestionsVisible && IANA_TIMEZONES.map((timezone) => <option key={timezone} value={timezone} />)}
          </datalist>
          <p className="form-help">{copy.timezoneHelp}</p>

          <button className="primary-button organization-submit" type="submit" disabled={!hasChanges || submitting || !draft.name.trim() || !draft.timezone.trim()}>
            {submitting ? <><LoaderCircle className="spin" size={18} /> {copy.saving}</> : copy.save}
          </button>
        </form>
      </section>}
    </div>
  </main>
}
