import { Building2 } from '../../icons'


export function AccessDeniedPage({ onLogout }) {
  return <main className="login-page">
    <section className="login-card" aria-labelledby="access-denied-title">
      <div className="login-brand" aria-hidden="true"><Building2 size={25} /></div>
      <p className="eyebrow">Prospect CRM</p>
      <h1 id="access-denied-title">Accès non autorisé</h1>
      <p className="login-intro">Votre rôle ne permet pas d’utiliser cette fonctionnalité.</p>
      <button className="secondary-button full-width" type="button" onClick={onLogout}>Se déconnecter</button>
    </section>
  </main>
}
