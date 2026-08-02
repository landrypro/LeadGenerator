import { useEffect, useRef, useState } from 'react'

import { Building2 } from '../../icons'
import { navigate } from '../../app/navigation'
import { CRM_PATHS } from '../../app/routes'
import { invitationApi } from './api/invitationApi'


const ERROR_MESSAGES = Object.freeze({
  invitation_invalid: 'Cette invitation est invalide, expirée ou a déjà été utilisée.',
  invitation_account_mismatch: 'Déconnectez-vous, puis utilisez le compte destinataire de l’invitation.',
  membership_reactivation_required: 'Une appartenance désactivée doit être réactivée par un administrateur.',
  invitation_rate_limited: 'Trop de tentatives. Veuillez réessayer plus tard.',
  invitation_service_unavailable: 'Le service d’invitation est temporairement indisponible.',
  session_creation_failed_after_acceptance: 'Invitation acceptée. Reconnectez-vous lorsque le service sera disponible.',
})


export function InvitationPage({ initialToken, auth }) {
  const tokenRef = useRef(initialToken)
  const previewOperation = useRef(null)
  const [preview, setPreview] = useState(null)
  const [state, setState] = useState(initialToken ? 'loading' : 'invalid')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!tokenRef.current) return undefined
    if (!previewOperation.current) {
      const controller = new AbortController()
      previewOperation.current = {
        abortTimer: null,
        controller,
        promise: invitationApi.preview(tokenRef.current, controller.signal),
      }
    }
    const operation = previewOperation.current
    if (operation.abortTimer !== null) {
      clearTimeout(operation.abortTimer)
      operation.abortTimer = null
    }
    let active = true
    operation.promise
      .then((result) => {
        if (!active) return
        setPreview(result)
        setState('ready')
      })
      .catch((previewError) => {
        if (!active || previewError?.name === 'AbortError') return
        tokenRef.current = ''
        setError(messageFor(previewError))
        setState('invalid')
      })
    return () => {
      active = false
      operation.abortTimer = setTimeout(() => operation.controller.abort(), 0)
    }
  }, [])

  function accepted(session) {
    tokenRef.current = ''
    auth?.adoptSession(session)
    navigate(CRM_PATHS.home)
  }

  return <main className="invitation-page">
    <section className="invitation-card" aria-labelledby="invitation-title">
      <header className="invitation-header">
        <div className="login-brand" aria-hidden="true"><Building2 size={25} /></div>
        <div><p className="eyebrow">Prospect CRM</p><h1 id="invitation-title">Invitation</h1></div>
      </header>
      {state === 'loading' && <p className="invitation-status" role="status">Vérification de l’invitation…</p>}
      {state === 'invalid' && <TerminalInvitationState message={error} />}
      {state === 'ready' && preview && <InvitationFlow
        preview={preview}
        auth={auth}
        tokenRef={tokenRef}
        onAccepted={accepted}
      />}
    </section>
  </main>
}


function InvitationFlow({ preview, auth, tokenRef, onAccepted }) {
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [email, setEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const session = auth?.session

  async function run(operation) {
    setWorking(true)
    setError('')
    try {
      await operation()
    } catch (operationError) {
      setError(messageFor(operationError))
    } finally {
      setWorking(false)
    }
  }

  async function createAccount(event) {
    event.preventDefault()
    if (password !== confirmation) {
      setError('Les deux mots de passe doivent être identiques.')
      return
    }
    await run(async () => onAccepted(
      await invitationApi.acceptNewAccount(tokenRef.current, displayName, password),
    ))
  }

  async function login(event) {
    event.preventDefault()
    await run(() => auth.login(email, loginPassword))
  }

  async function acceptExisting() {
    await run(async () => onAccepted(await invitationApi.acceptExistingAccount(tokenRef.current)))
  }

  return <>
    <div className="invitation-summary">
      <strong>{preview.organization_name}</strong>
      <span>Rôle proposé : {roleLabel(preview.role)}</span>
      <small>Valide jusqu’au {new Date(preview.expires_at).toLocaleString('fr-CA')}</small>
    </div>
    {error && <div className="error-banner" role="alert"><span>{error}</span></div>}
    {!preview.existing_account && session && <SessionConflict onLogout={auth.logout} />}
    {!preview.existing_account && !session && <form onSubmit={createAccount}>
      <p className="invitation-copy">Créez votre compte pour rejoindre l’organisation.</p>
      <InvitationField id="invitation-name" label="Nom affiché" value={displayName} onChange={setDisplayName}
        autoComplete="name" maxLength={120} />
      <InvitationField id="invitation-password" label="Mot de passe" value={password} onChange={setPassword}
        type="password" autoComplete="new-password" minLength={12} maxLength={128} />
      <InvitationField id="invitation-password-confirmation" label="Confirmer le mot de passe" value={confirmation}
        onChange={setConfirmation} type="password" autoComplete="new-password" minLength={12} maxLength={128} />
      <button className="primary-button invitation-action" type="submit" disabled={working}>
        {working ? 'Traitement…' : 'Créer le compte et accepter'}
      </button>
    </form>}
    {preview.existing_account && !session && auth?.status !== 'loading' && <form onSubmit={login}>
      <p className="invitation-copy">Connectez-vous avec le compte destinataire, sans quitter cette page.</p>
      <InvitationField id="invitation-email" label="Adresse courriel" value={email} onChange={setEmail}
        type="email" autoComplete="username" maxLength={254} />
      <InvitationField id="invitation-login-password" label="Mot de passe" value={loginPassword}
        onChange={setLoginPassword} type="password" autoComplete="current-password" maxLength={128} />
      <button className="primary-button invitation-action" type="submit" disabled={working}>
        {working ? 'Connexion…' : 'Se connecter'}
      </button>
    </form>}
    {preview.existing_account && auth?.status === 'loading' &&
      <p className="invitation-status" role="status">Vérification de votre session…</p>}
    {preview.existing_account && session && <div>
      <p className="invitation-copy">Compte connecté : <strong>{session.user.display_name}</strong></p>
      <button className="primary-button invitation-action" type="button" disabled={working} onClick={acceptExisting}>
        {working ? 'Traitement…' : 'Accepter l’invitation'}
      </button>
      <button className="invitation-logout" type="button" onClick={auth.logout}>Utiliser un autre compte</button>
    </div>}
  </>
}


function InvitationField({ id, label, value, onChange, type = 'text', ...attributes }) {
  return <label className="login-field" htmlFor={id}>
    <span>{label}</span>
    <input id={id} type={type} value={value} onChange={(event) => onChange(event.target.value)} required {...attributes} />
  </label>
}


function SessionConflict({ onLogout }) {
  return <div className="invitation-conflict">
    <p>Déconnectez-vous avant de créer le compte associé à cette invitation.</p>
    <button className="secondary-button full-width" type="button" onClick={onLogout}>Se déconnecter</button>
  </div>
}


function TerminalInvitationState({ message }) {
  return <div className="invitation-terminal" role="alert">
    <h2>Invitation non disponible</h2>
    <p>{message || 'Le lien est absent ou mal formé. Utilisez le lien complet reçu par courriel.'}</p>
  </div>
}


function messageFor(error) {
  return ERROR_MESSAGES[error?.code] || error?.message || 'Une erreur inattendue est survenue.'
}


function roleLabel(role) {
  return ({ admin: 'Administrateur', manager: 'Gestionnaire', sales: 'Commercial' })[role] || 'Membre'
}
