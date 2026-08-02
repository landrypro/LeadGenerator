import { PlaceSearchPage } from '../features/lead-search/LeadGeneratorPage'

export const CRM_PATHS = Object.freeze({
  home: '/',
  login: '/login',
  dashboard: '/dashboard',
  prospects: '/prospects',
  pipeline: '/pipeline',
  activities: '/activities',
  actions: '/actions',
  opportunities: '/opportunities',
  compliance: '/compliance',
  importsExports: '/imports-exports',
  administration: '/administration',
  acceptInvitation: '/accept-invitation',
})

// Les chemins CRM sont réservés ci-dessus. Ils seront activés au fur et à mesure
// que leurs pages seront développées, sans modifier le composant racine.
export const routes = [
  { id: 'google-place-search', path: CRM_PATHS.home, Component: PlaceSearchPage },
]
