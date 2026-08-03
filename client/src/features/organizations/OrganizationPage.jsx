import { useEffect, useMemo, useRef, useState } from 'react'

import { Building2, Check, LoaderCircle } from '../../icons'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { organizationApi } from './api/organizationApi'
import { useOrganization } from './hooks/useOrganization'


const STATUS_LABELS = Object.freeze({
  active: 'Active',
  provisioning: 'En cours d’activation',
  suspended: 'Suspendue',
})

const TIMEZONE_SUGGESTIONS = Object.freeze([
  'America/Toronto',
  'America/Montreal',
  'America/Vancouver',
  'America/Edmonton',
  'America/Winnipeg',
  'America/Halifax',
  'America/St_Johns',
])


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
  const { organization, setOrganization, loading, error: loadError, load } = useOrganization()
  const [draft, setDraft] = useState({ name: '', locale: 'fr-CA', timezone: 'America/Toronto' })
  const [submitting, setSubmitting] = useState(false)
  const [mutationError, setMutationError] = useState('')
  const [conflictVersion, setConflictVersion] = useState('')
  const [success, setSuccess] = useState('')
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
    if (!organization || !hasChanges || submitting) return
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
      setSuccess('Les informations de l’organisation ont été enregistrées.')
    } catch (updateError) {
      if (updateError?.name === 'AbortError' || mutationSequenceRef.current !== sequence) return
      if (updateError?.code === 'organization_version_conflict') {
        setConflictVersion(updateError.fields?.version ?? 'inconnue')
      } else {
        setMutationError(toUserMessage(updateError, 'Impossible de modifier l’organisation.'))
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
      setSuccess('La version actuelle a été chargée. Vérifiez vos modifications avant de les saisir à nouveau.')
    }
  }

  if (loading && !organization) {
    return <main className="administration-page organization-page" aria-live="polite">
      <div className="administration-loading"><LoaderCircle className="spin" size={20} /> Chargement de l’organisation…</div>
    </main>
  }

  if (!organization) {
    return <main className="administration-page organization-page" aria-labelledby="organization-error-title">
      <section className="route-status-card">
        <p className="eyebrow">Administration</p>
        <h1 id="organization-error-title">Organisation indisponible</h1>
        <p>{loadError || 'Impossible de charger l’organisation.'}</p>
        <button className="secondary-button" type="button" onClick={load}>Réessayer</button>
      </section>
    </main>
  }

  return <main className="administration-page organization-page" aria-labelledby="organization-title">
    <header className="administration-page-heading">
      <p className="eyebrow">Administration</p>
      <h1 id="organization-title">Organisation</h1>
      <p>Consultez les informations de l’organisation active{canUpdate ? ' et mettez-les à jour.' : '.'}</p>
    </header>

    {loadError && <ErrorBanner><span>{loadError}</span></ErrorBanner>}
    {mutationError && <ErrorBanner><span>{mutationError}</span></ErrorBanner>}
    {success && <div className="success-banner" role="status"><Check size={18} /><span>{success}</span></div>}
    {conflictVersion && <section className="conflict-banner" role="alert" aria-labelledby="organization-conflict-title">
      <h2 id="organization-conflict-title">Une version plus récente existe</h2>
      <p>
        Votre saisie est conservée. Version chargée : {organization.version}. Version actuelle signalée : {conflictVersion}.
      </p>
      <button className="secondary-button" type="button" onClick={reloadAfterConflict} disabled={loading}>
        {loading ? 'Rechargement…' : 'Recharger la version actuelle'}
      </button>
    </section>}

    <div className="organization-grid">
      <section className="administration-card" aria-labelledby="organization-summary-title">
        <div className="administration-card-icon" aria-hidden="true"><Building2 size={22} /></div>
        <h2 id="organization-summary-title">Informations actuelles</h2>
        <dl className="account-details organization-details">
          <div><dt>Nom</dt><dd>{organization.name}</dd></div>
          <div><dt>Langue</dt><dd>{organization.locale === 'fr-CA' ? 'Français (Canada)' : 'English (Canada)'}</dd></div>
          <div><dt>Fuseau horaire</dt><dd>{organization.timezone}</dd></div>
          <div><dt>État</dt><dd><span className={`organization-status ${organization.status}`}>{STATUS_LABELS[organization.status] ?? organization.status}</span></dd></div>
          <div><dt>Créée le</dt><dd><time dateTime={organization.created_at}>{formatDate(organization.created_at, organization.locale, organization.timezone)}</time></dd></div>
          <div><dt>Mise à jour le</dt><dd><time dateTime={organization.updated_at}>{formatDate(organization.updated_at, organization.locale, organization.timezone)}</time></dd></div>
        </dl>
      </section>

      {canUpdate && <section className="administration-card" aria-labelledby="organization-edit-title">
        <h2 id="organization-edit-title">Modifier l’organisation</h2>
        <form className="organization-form" onSubmit={submit}>
          <label htmlFor="organization-name">Nom</label>
          <input id="organization-name" value={draft.name} onChange={(event) => updateDraft('name', event.target.value)} minLength="1" maxLength="160" required />

          <label htmlFor="organization-locale">Langue</label>
          <select id="organization-locale" value={draft.locale} onChange={(event) => updateDraft('locale', event.target.value)}>
            <option value="fr-CA">Français (Canada)</option>
            <option value="en-CA">English (Canada)</option>
          </select>

          <label htmlFor="organization-timezone">Fuseau horaire IANA</label>
          <input id="organization-timezone" list="organization-timezones" value={draft.timezone} onChange={(event) => updateDraft('timezone', event.target.value)} minLength="1" maxLength="64" required />
          <datalist id="organization-timezones">
            {TIMEZONE_SUGGESTIONS.map((timezone) => <option key={timezone} value={timezone} />)}
          </datalist>

          <button className="primary-button organization-submit" type="submit" disabled={!hasChanges || submitting || !draft.name.trim() || !draft.timezone.trim()}>
            {submitting ? <><LoaderCircle className="spin" size={18} /> Enregistrement…</> : 'Enregistrer les modifications'}
          </button>
        </form>
      </section>}
    </div>
  </main>
}
