import { useEffect, useRef, useState } from 'react'

import { toUserMessage } from '../../../shared/api/errors'
import { createRequestId } from '../../../shared/ids/requestId'
import { ErrorBanner } from '../../../shared/ui/Feedback'
import { platformApi } from '../api/platformApi'
import { resolveDefaultTimezone } from '../defaultTimezone'


const blankForm = () => ({ name: '', locale: 'fr-CA', timezone: resolveDefaultTimezone(), email: '' })


export function ProvisionOrganizationForm({ createId = createRequestId, onProvisioned }) {
  const [form, setForm] = useState(blankForm)
  const [intent, setIntent] = useState(null)
  const [blocked, setBlocked] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })
  const controllerRef = useRef(null)
  const pendingRef = useRef(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      controllerRef.current?.abort()
    }
  }, [])

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
    setIntent(null)
    setBlocked(false)
    setMessage({ type: '', text: '' })
  }

  async function submit(event) {
    event.preventDefault()
    if (pendingRef.current || blocked || !isValid(form)) return
    pendingRef.current = true
    const currentIntent = intent ?? { id: createId(), payload: normalize(form) }
    if (!intent) setIntent(currentIntent)
    const controller = new AbortController()
    controllerRef.current = controller
    setSubmitting(true)
    setMessage({ type: '', text: '' })
    try {
      const view = await platformApi.createOrganization({ ...currentIntent.payload, creation_request_id: currentIntent.id }, controller.signal)
      if (controller.signal.aborted || !mountedRef.current) return
      onProvisioned(view)
      setForm(blankForm())
      setIntent(null)
      setBlocked(false)
      const text = view.first_invitation.delivery_status === 'failed'
        ? 'L’organisation a été créée, mais la livraison a échoué. Utilisez le renvoi dans la liste.'
        : view.replayed ? 'L’intention existante a été retrouvée sans créer de doublon.' : 'L’organisation et son invitation initiale ont été créées.'
      setMessage({ type: 'success', text })
    } catch (error) {
      if (error?.name === 'AbortError' || !mountedRef.current) return
      if (error?.code === 'idempotency_key_reused') setBlocked(true)
      setMessage({ type: 'error', text: creationErrorMessage(error) })
    } finally {
      controllerRef.current = null
      pendingRef.current = false
      if (mountedRef.current) setSubmitting(false)
    }
  }

  function abandonIntent() {
    setIntent(null)
    setBlocked(false)
    setMessage({ type: 'status', text: 'Une nouvelle intention sera créée lors de la prochaine soumission.' })
  }

  return <section className="administration-card platform-provision-card" aria-labelledby="platform-provision-title">
    <h2 id="platform-provision-title">Provisionner une organisation</h2>
    <p>L’administrateur initial recevra un lien à usage unique. Aucun jeton n’est affiché ou conservé dans le navigateur.</p>
    {message.text && (message.type === 'error'
      ? <ErrorBanner compact><span>{message.text}</span></ErrorBanner>
      : <div className="success-banner" role="status"><span>{message.text}</span></div>)}
    <form className="platform-provision-form" onSubmit={submit}>
      <Field label="Nom de l’organisation" id="platform-organization-name"><input id="platform-organization-name" value={form.name} onChange={(event) => update('name', event.target.value)} maxLength="160" disabled={submitting} required /></Field>
      <Field label="Langue" id="platform-organization-locale"><select id="platform-organization-locale" value={form.locale} onChange={(event) => update('locale', event.target.value)} disabled={submitting}><option value="fr-CA">Français (Canada)</option><option value="en-CA">English (Canada)</option></select></Field>
      <Field label="Fuseau horaire IANA" id="platform-organization-timezone"><input id="platform-organization-timezone" value={form.timezone} onChange={(event) => update('timezone', event.target.value)} maxLength="64" disabled={submitting} required /></Field>
      <Field label="Courriel de l’administrateur initial" id="platform-administrator-email"><input id="platform-administrator-email" type="email" autoComplete="email" value={form.email} onChange={(event) => update('email', event.target.value)} maxLength="254" disabled={submitting} required /></Field>
      <div className="platform-provision-actions">
        <button className="primary-button" type="submit" disabled={submitting || blocked || !isValid(form)}>{submitting ? 'Provisionnement…' : intent ? 'Réessayer la même intention' : 'Créer l’organisation'}</button>
        {blocked && <button className="secondary-button" type="button" onClick={abandonIntent}>Abandonner cette intention</button>}
      </div>
    </form>
  </section>
}


function Field({ children, id, label }) {
  return <div className="platform-form-field"><label htmlFor={id}>{label}</label>{children}</div>
}


const isValid = (form) => Boolean(form.name.trim() && form.timezone.trim() && form.email.trim())


function normalize(form) {
  return { name: form.name.trim().replace(/\s+/g, ' '), locale: form.locale, timezone: form.timezone.trim(), first_administrator_email: form.email.trim() }
}


function creationErrorMessage(error) {
  if (error?.code === 'provisioning_outcome_unknown') return 'Le résultat est incertain. Réessayez sans modifier le formulaire pour conserver exactement la même intention.'
  if (error?.code === 'idempotency_key_reused') return 'Cette clé a servi à une autre commande. Abandonnez explicitement cette intention avant d’en créer une nouvelle.'
  return toUserMessage(error, 'Le provisioning a échoué.')
}
