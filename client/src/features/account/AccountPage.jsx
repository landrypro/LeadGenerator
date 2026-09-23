import { Building2, LogOut, UsersRound } from '../../icons'


const ACCOUNT_MESSAGES = Object.freeze({
  'fr-CA': Object.freeze({
    eyebrow: 'Espace personnel', title: 'Mon compte', description: 'Consultez votre identité et les organisations auxquelles vous avez accès.',
    identity: 'Identité', displayName: 'Nom affiché', email: 'Adresse courriel', platformRole: 'Rôle plateforme', organizations: 'Organisations',
    activeOrganization: 'Organisation active', active: 'Active', noMembership: 'Aucune appartenance active.', session: 'Session',
    sessionDescription: 'Les informations de session demeurent en mémoire et ne sont pas enregistrées dans le navigateur.', logout: 'Se déconnecter',
    roles: Object.freeze({ admin: 'Administrateur', manager: 'Gestionnaire', sales: 'Commercial', platform_admin: 'Administrateur de plateforme' }),
  }),
  'en-CA': Object.freeze({
    eyebrow: 'Personal workspace', title: 'My account', description: 'View your identity and the organizations you can access.',
    identity: 'Identity', displayName: 'Display name', email: 'Email address', platformRole: 'Platform role', organizations: 'Organizations',
    activeOrganization: 'Active organization', active: 'Active', noMembership: 'No active memberships.', session: 'Session',
    sessionDescription: 'Session information stays in memory and is not stored in the browser.', logout: 'Sign out',
    roles: Object.freeze({ admin: 'Administrator', manager: 'Manager', sales: 'Sales', platform_admin: 'Platform administrator' }),
  }),
})


function accountMessages(locale) {
  return ACCOUNT_MESSAGES[locale] ?? ACCOUNT_MESSAGES['fr-CA']
}


export function AccountPage({ session, onLogout }) {
  const memberships = session.memberships ?? []
  const copy = accountMessages(session.active_organization?.locale)

  return <main className="administration-page account-page" aria-labelledby="account-title">
    <header className="administration-page-heading">
      <p className="eyebrow">{copy.eyebrow}</p>
      <h1 id="account-title">{copy.title}</h1>
      <p>{copy.description}</p>
    </header>

    <div className="account-grid">
      <section className="administration-card" aria-labelledby="identity-title">
        <div className="administration-card-icon" aria-hidden="true"><UsersRound size={22} /></div>
        <h2 id="identity-title">{copy.identity}</h2>
        <dl className="account-details">
          <div><dt>{copy.displayName}</dt><dd>{session.user.display_name}</dd></div>
          <div><dt>{copy.email}</dt><dd>{session.user.email}</dd></div>
          {session.user.platform_role && <div>
            <dt>{copy.platformRole}</dt><dd>{copy.roles[session.user.platform_role] ?? session.user.platform_role}</dd>
          </div>}
        </dl>
      </section>

      <section className="administration-card" aria-labelledby="organizations-title">
        <div className="administration-card-icon lime" aria-hidden="true"><Building2 size={22} /></div>
        <h2 id="organizations-title">{copy.organizations}</h2>
        {session.active_organization && <p className="account-active-organization">
          {copy.activeOrganization} <strong>{session.active_organization.name}</strong>
        </p>}
        {memberships.length > 0 ? <ul className="membership-list">
          {memberships.map((membership) => <li key={membership.id}>
            <span><strong>{membership.organization.name}</strong><small>{copy.roles[membership.role] ?? membership.role}</small></span>
            {membership.organization.id === session.active_organization?.id && <span className="current-badge">{copy.active}</span>}
          </li>)}
        </ul> : <p className="administration-empty">{copy.noMembership}</p>}
      </section>
    </div>

    <section className="administration-card account-security" aria-labelledby="security-title">
      <h2 id="security-title">{copy.session}</h2>
      <p>{copy.sessionDescription}</p>
      <button className="secondary-button account-logout" type="button" onClick={onLogout}>
        <LogOut size={17} /> {copy.logout}
      </button>
    </section>
  </main>
}
