import { useState } from 'react'

import { Building2 } from '../../icons'
import { ErrorBanner } from '../../shared/ui/Feedback'


const LOGIN_MESSAGES = Object.freeze({
  'fr-CA': Object.freeze({ title: 'Connexion', intro: 'Accédez à votre espace sécurisé de gestion des prospects.', email: 'Adresse courriel', password: 'Mot de passe', loading: 'Connexion…', submit: 'Se connecter', help: 'L’accès est réservé aux comptes créés par un administrateur.', error: 'La connexion a échoué.', language: 'Langue', french: 'Français (Canada)', english: 'English (Canada)' }),
  'en-CA': Object.freeze({ title: 'Sign in', intro: 'Access your secure prospect-management workspace.', email: 'Email address', password: 'Password', loading: 'Signing in…', submit: 'Sign in', help: 'Access is reserved for accounts created by an administrator.', error: 'Sign-in failed.', incorrectCredentials: 'Incorrect email address or password.', language: 'Language', french: 'Français (Canada)', english: 'English (Canada)' }),
})

export function LoginPage({ locale = 'fr-CA', onLocaleChange, onLogin }) {
  const copy = LOGIN_MESSAGES[locale] ?? LOGIN_MESSAGES['fr-CA']
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      await onLogin(email, password)
    } catch (loginError) {
      setError(locale === 'en-CA'
        ? (loginError?.code === 'authentication_failed' ? copy.incorrectCredentials : copy.error)
        : (loginError?.message || copy.error))
    } finally {
      setLoading(false)
    }
  }

  return <main className="login-page">
    <section className="login-card" aria-labelledby="login-title">
      <div className="login-brand" aria-hidden="true"><Building2 size={25} /></div>
      <p className="eyebrow">Marketteo CRM</p>
      <h1 id="login-title">{copy.title}</h1>
      <p className="login-intro">{copy.intro}</p>
      {error && <ErrorBanner><span>{error}</span></ErrorBanner>}
      <form onSubmit={submit}>
        <label className="login-field" htmlFor="login-email">
          <span>{copy.email}</span>
          <input id="login-email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} maxLength="254" autoFocus required />
        </label>
        <label className="login-field" htmlFor="login-password">
          <span>{copy.password}</span>
          <input id="login-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} maxLength="128" required />
        </label>
        <button className="primary-button login-submit" type="submit" disabled={loading}>
          {loading ? copy.loading : copy.submit}
        </button>
      </form>
      <label className="login-field" htmlFor="public-locale"><span>{copy.language}</span><select id="public-locale" value={locale} onChange={(event) => onLocaleChange?.(event.target.value)}><option value="fr-CA">{copy.french}</option><option value="en-CA">{copy.english}</option></select></label>
      <p className="login-help">{copy.help}</p>
    </section>
  </main>
}
