import { useState } from 'react'

import { Building2 } from '../../icons'


export function LoginPage({ onLogin }) {
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
      setError(loginError?.message || 'La connexion a échoué.')
    } finally {
      setLoading(false)
    }
  }

  return <main className="login-page">
    <section className="login-card" aria-labelledby="login-title">
      <div className="login-brand" aria-hidden="true"><Building2 size={25} /></div>
      <p className="eyebrow">Prospect CRM</p>
      <h1 id="login-title">Connexion</h1>
      <p className="login-intro">Accédez à votre espace sécurisé de gestion des prospects.</p>
      {error && <div className="error-banner" role="alert"><span>{error}</span></div>}
      <form onSubmit={submit}>
        <label className="login-field" htmlFor="login-email">
          <span>Adresse courriel</span>
          <input id="login-email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} maxLength="254" autoFocus required />
        </label>
        <label className="login-field" htmlFor="login-password">
          <span>Mot de passe</span>
          <input id="login-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} maxLength="128" required />
        </label>
        <button className="primary-button login-submit" type="submit" disabled={loading}>
          {loading ? 'Connexion…' : 'Se connecter'}
        </button>
      </form>
      <p className="login-help">L’accès est réservé aux comptes créés par un administrateur.</p>
    </section>
  </main>
}
