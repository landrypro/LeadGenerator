import { Building2, LogOut, UsersRound } from '../../icons'


const ROLE_LABELS = Object.freeze({
  admin: 'Administrateur',
  manager: 'Gestionnaire',
  sales: 'Commercial',
  platform_admin: 'Administrateur de plateforme',
})


function roleLabel(role) {
  return ROLE_LABELS[role] ?? role
}


export function AccountPage({ session, onLogout }) {
  const memberships = session.memberships ?? []

  return <main className="administration-page account-page" aria-labelledby="account-title">
    <header className="administration-page-heading">
      <p className="eyebrow">Espace personnel</p>
      <h1 id="account-title">Mon compte</h1>
      <p>Consultez votre identité et les organisations auxquelles vous avez accès.</p>
    </header>

    <div className="account-grid">
      <section className="administration-card" aria-labelledby="identity-title">
        <div className="administration-card-icon" aria-hidden="true"><UsersRound size={22} /></div>
        <h2 id="identity-title">Identité</h2>
        <dl className="account-details">
          <div><dt>Nom affiché</dt><dd>{session.user.display_name}</dd></div>
          <div><dt>Adresse courriel</dt><dd>{session.user.email}</dd></div>
          {session.user.platform_role && <div>
            <dt>Rôle plateforme</dt><dd>{roleLabel(session.user.platform_role)}</dd>
          </div>}
        </dl>
      </section>

      <section className="administration-card" aria-labelledby="organizations-title">
        <div className="administration-card-icon lime" aria-hidden="true"><Building2 size={22} /></div>
        <h2 id="organizations-title">Organisations</h2>
        {session.active_organization && <p className="account-active-organization">
          Organisation active <strong>{session.active_organization.name}</strong>
        </p>}
        {memberships.length > 0 ? <ul className="membership-list">
          {memberships.map((membership) => <li key={membership.id}>
            <span><strong>{membership.organization.name}</strong><small>{roleLabel(membership.role)}</small></span>
            {membership.organization.id === session.active_organization?.id && <span className="current-badge">Active</span>}
          </li>)}
        </ul> : <p className="administration-empty">Aucune appartenance active.</p>}
      </section>
    </div>

    <section className="administration-card account-security" aria-labelledby="security-title">
      <h2 id="security-title">Session</h2>
      <p>Les informations de session demeurent en mémoire et ne sont pas enregistrées dans le navigateur.</p>
      <button className="secondary-button account-logout" type="button" onClick={onLogout}>
        <LogOut size={17} /> Se déconnecter
      </button>
    </section>
  </main>
}
