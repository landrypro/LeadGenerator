import { useRef, useState } from 'react'

import { LoaderCircle } from '../../icons'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { followInternalLink } from '../../app/navigation'
import { prospectApi } from './api/prospectApi'

const PROSPECTS_PATH = '/app/prospects'


export function CreateProspectPage() {
  const [internalAlias, setInternalAlias] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const controllerRef = useRef(null)

  async function submit(event) {
    event.preventDefault()
    if (!internalAlias.trim() || submitting) return
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setSubmitting(true)
    setError('')
    try {
      await prospectApi.create({ internal_alias: internalAlias.trim() }, controller.signal)
      window.history.back()
    } catch (requestError) {
      if (requestError?.name !== 'AbortError') setError(toUserMessage(requestError, 'Impossible de créer le prospect.'))
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null
      setSubmitting(false)
    }
  }

  return <main className="administration-page prospects-page" aria-labelledby="create-prospect-title">
    <header className="administration-page-heading"><p className="eyebrow">Portefeuille CRM</p><h1 id="create-prospect-title">Ajouter un prospect</h1><p>Créez un établissement suivi dans votre organisation. Vous pourrez enrichir son profil dans l’étape suivante.</p></header>
    <section className="administration-card prospect-create-card">
      {error && <ErrorBanner><span>{error}</span></ErrorBanner>}
      <form className="organization-form" onSubmit={submit}>
        <label htmlFor="prospect-internal-alias">Nom interne de l’établissement</label>
        <input id="prospect-internal-alias" value={internalAlias} onChange={(event) => setInternalAlias(event.target.value)} minLength="1" maxLength="160" autoFocus required />
        <p className="form-help">Cette saisie est une donnée CRM manuelle. Elle ne copie aucune information depuis Google.</p>
        <div className="prospect-form-actions"><a className="secondary-button" href={PROSPECTS_PATH} onClick={(event) => followInternalLink(event, PROSPECTS_PATH)}>Annuler</a><button className="primary-button" type="submit" disabled={submitting || !internalAlias.trim()}>{submitting ? <><LoaderCircle className="spin" size={18} /> Création…</> : 'Créer le prospect'}</button></div>
      </form>
    </section>
  </main>
}
