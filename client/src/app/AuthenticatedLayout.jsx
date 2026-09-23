import { useEffect, useRef, useState } from 'react'

import { Building2, ExternalLink, LogOut, Menu, X } from '../icons'
import { OrganizationSwitcher } from '../features/organizations/OrganizationSwitcher'
import { followInternalLink } from './navigation'
import { CRM_PATHS, localizedRouteLabel, localizedRouteTitle, navigationRoutes } from './routes'


export function AuthenticatedLayout({
  children,
  currentRoute,
  session,
  onLogout,
  onSwitchOrganization,
  switchingOrganization = false,
}) {
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false)
  const menuButtonRef = useRef(null)
  const closeButtonRef = useRef(null)
  const availableRoutes = navigationRoutes(session)
  const locale = session.active_organization?.locale ?? 'fr-CA'
  const copy = locale === 'en-CA' ? { skip: 'Skip to main content', home: 'Marketteo CRM — Home', crm: 'Sales CRM', navigation: 'Navigation', closeNavigation: 'Close navigation', mainNavigation: 'Main navigation', manual: 'Manual', signOut: 'Sign out', breadcrumb: 'Breadcrumb' } : { skip: 'Aller au contenu principal', home: 'Marketteo CRM — Accueil', crm: 'CRM commercial', navigation: 'Navigation', closeNavigation: 'Fermer la navigation', mainNavigation: 'Navigation principale', manual: 'Manuel', signOut: 'Se déconnecter', breadcrumb: 'Fil d’Ariane' }

  useEffect(() => {
    if (!mobileNavigationOpen) return undefined
    closeButtonRef.current?.focus()
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') {
        setMobileNavigationOpen(false)
        menuButtonRef.current?.focus()
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [mobileNavigationOpen])

  function closeNavigation() {
    setMobileNavigationOpen(false)
  }

  function closeNavigationAndRestoreFocus() {
    closeNavigation()
    menuButtonRef.current?.focus()
  }

  return <div className="authenticated-app">
    <a className="skip-link" href="#route-content">{copy.skip}</a>
    <header className="authenticated-header">
      <a
        className="authenticated-brand"
        href={availableRoutes[0]?.path ?? CRM_PATHS.account}
        onClick={(event) => followInternalLink(event, availableRoutes[0]?.path ?? CRM_PATHS.account)}
        aria-label={copy.home}
      >
        <span className="authenticated-brand-mark" aria-hidden="true"><Building2 size={20} /></span>
        <span><strong>Marketteo</strong><small>{copy.crm}</small></span>
      </a>

      <button
        ref={menuButtonRef}
        className="authenticated-menu-button"
        type="button"
        aria-expanded={mobileNavigationOpen}
        aria-controls="primary-navigation"
        onClick={() => setMobileNavigationOpen(true)}
      >
        <Menu size={19} /><span>Menu</span>
      </button>

      {mobileNavigationOpen && <button
        className="authenticated-navigation-backdrop"
        type="button"
        aria-hidden="true"
        tabIndex="-1"
        onClick={closeNavigationAndRestoreFocus}
      />}

      <div id="primary-navigation" className={`authenticated-navigation-panel ${mobileNavigationOpen ? 'open' : ''}`}>
        <div className="authenticated-navigation-mobile-heading">
          <strong>{copy.navigation}</strong>
          <button ref={closeButtonRef} type="button" onClick={closeNavigationAndRestoreFocus} aria-label={copy.closeNavigation}>
            <X size={18} />
          </button>
        </div>
        <nav className="authenticated-navigation" aria-label={copy.mainNavigation}>
          {availableRoutes.map((route) => <a
            key={route.id}
            href={route.path}
            aria-current={currentRoute?.id === route.id ? 'page' : undefined}
            onClick={(event) => {
              followInternalLink(event, route.path)
              closeNavigation()
            }}
          >{localizedRouteLabel(route, locale)}</a>)}
        </nav>
      </div>

      <div className="authenticated-context">
        <OrganizationSwitcher
          session={session}
          switching={switchingOrganization}
          onSwitch={onSwitchOrganization}
        />
        <a
          className="authenticated-user"
          href={CRM_PATHS.account}
          aria-current={currentRoute?.id === 'account' ? 'page' : undefined}
          onClick={(event) => followInternalLink(event, CRM_PATHS.account)}
        >{session.user.display_name}</a>
        <a
          className="authenticated-manual-link"
          href="/manuel-utilisateur/index.html"
          target="_blank"
          rel="noopener noreferrer"
        ><ExternalLink size={15} /><span>{copy.manual}</span></a>
        <button className="authenticated-logout" type="button" onClick={onLogout} aria-label={copy.signOut}>
          <LogOut size={17} />
        </button>
      </div>
    </header>

    <nav className="route-breadcrumb" aria-label={copy.breadcrumb}>
      <span>Marketteo CRM</span><span aria-hidden="true">/</span><strong>{localizedRouteTitle(currentRoute, locale) || (locale === 'en-CA' ? 'Page not found' : 'Page introuvable')}</strong>
    </nav>
    <div id="route-content" className="route-content" tabIndex="-1">{children}</div>
  </div>
}
