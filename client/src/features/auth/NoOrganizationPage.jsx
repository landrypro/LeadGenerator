import { Building2 } from '../../icons'


const NO_ORGANIZATION_MESSAGES = Object.freeze({
  'fr-CA': Object.freeze({ title: 'Aucune organisation accessible', intro: 'Ce compte est actif, mais ne possède encore aucune appartenance. Revenez au lien reçu par courriel pour accepter votre invitation.', logout: 'Se déconnecter' }),
  'en-CA': Object.freeze({ title: 'No organization available', intro: 'This account is active but does not yet belong to an organization. Return to the link received by email to accept your invitation.', logout: 'Sign out' }),
})

export function NoOrganizationPage({ locale = 'fr-CA', onLogout }) {
  const copy = NO_ORGANIZATION_MESSAGES[locale] ?? NO_ORGANIZATION_MESSAGES['fr-CA']
  return <main className="login-page">
    <section className="login-card" aria-labelledby="no-organization-title">
      <div className="login-brand" aria-hidden="true"><Building2 size={25} /></div>
      <p className="eyebrow">Marketteo CRM</p>
      <h1 id="no-organization-title">{copy.title}</h1>
      <p className="login-intro">{copy.intro}</p>
      <button className="secondary-button full-width" type="button" onClick={onLogout}>{copy.logout}</button>
    </section>
  </main>
}
