import { Columns3, Home, ListChecks, Menu, UsersRound } from '../icons'
import { localizedRouteLabel } from './routes'


const icons = {
  dashboard: Home,
  tasks: ListChecks,
  prospects: UsersRound,
  pipeline: Columns3,
}

const labels = {
  'fr-CA': { dashboard: 'Accueil', tasks: 'Tâches', prospects: 'Prospects', pipeline: 'Pipeline', more: 'Plus', navigation: 'Navigation mobile' },
  'en-CA': { dashboard: 'Home', tasks: 'Tasks', prospects: 'Prospects', pipeline: 'Pipeline', more: 'More', navigation: 'Mobile navigation' },
}

export function MobileNavigationBar({ routes, activeId, locale, navigationOpen, onNavigate, onOpenNavigation }) {
  const copy = labels[locale] ?? labels['fr-CA']
  const moreActive = navigationOpen || !routes.some(route => route.id === activeId)
  return <nav className="authenticated-mobile-navigation" aria-label={copy.navigation}
    style={{ '--mobile-navigation-items': routes.length + 1 }}>
    {routes.map(route => {
      const Icon = icons[route.id]
      return <a
        key={route.id}
        href={route.path}
        aria-current={activeId === route.id ? 'page' : undefined}
        aria-label={copy[route.id] ?? localizedRouteLabel(route, locale)}
        onClick={event => onNavigate(event, route)}
      >
        <Icon size={20} />
        <span>{copy[route.id] ?? localizedRouteLabel(route, locale)}</span>
      </a>
    })}
    <button
      type="button"
      className={moreActive ? 'is-active' : ''}
      aria-expanded={navigationOpen}
      aria-controls="primary-navigation"
      aria-label={copy.more}
      onClick={onOpenNavigation}
    >
      <Menu size={20} />
      <span>{copy.more}</span>
    </button>
  </nav>
}
