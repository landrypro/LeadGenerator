import { Building2 } from '../../icons'


export function NoOrganizationPage({ onLogout }) {
  return <main className="login-page">
    <section className="login-card" aria-labelledby="no-organization-title">
      <div className="login-brand" aria-hidden="true"><Building2 size={25} /></div>
      <p className="eyebrow">Marketteo CRM</p>
      <h1 id="no-organization-title">Aucune organisation accessible</h1>
      <p className="login-intro">
        Ce compte est actif, mais ne possède encore aucune appartenance. Revenez au lien reçu par courriel pour
        accepter votre invitation.
      </p>
      <button className="secondary-button full-width" type="button" onClick={onLogout}>Se déconnecter</button>
    </section>
  </main>
}
