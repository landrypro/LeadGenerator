import { followInternalLink } from '../../app/navigation'
import { Building2 } from '../../icons'


export function NotFoundPage({ homePath }) {
  return <main className="route-status-page" aria-labelledby="not-found-title">
    <section className="route-status-card">
      <div className="administration-card-icon" aria-hidden="true"><Building2 size={22} /></div>
      <p className="eyebrow">Erreur 404</p>
      <h1 id="not-found-title">Page introuvable</h1>
      <p>Cette adresse ne correspond à aucune page actuellement disponible dans Marketteo CRM.</p>
      <a className="secondary-button route-status-action" href={homePath} onClick={(event) => followInternalLink(event, homePath)}>
        Revenir à l’accueil
      </a>
    </section>
  </main>
}
