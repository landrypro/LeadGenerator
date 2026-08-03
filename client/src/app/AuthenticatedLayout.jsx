import { useEffect, useRef, useState } from 'react'

import { Building2, LogOut, Menu, X } from '../icons'
import { OrganizationSwitcher } from '../features/organizations/OrganizationSwitcher'
import { followInternalLink } from './navigation'
import { CRM_PATHS, navigationRoutes } from './routes'


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
    <a className="skip-link" href="#route-content">Aller au contenu principal</a>
    <header className="authenticated-header">
      <a
        className="authenticated-brand"
        href={availableRoutes[0]?.path ?? CRM_PATHS.account}
        onClick={(event) => followInternalLink(event, availableRoutes[0]?.path ?? CRM_PATHS.account)}
        aria-label="Prospect CRM — Accueil"
      >
        <span className="authenticated-brand-mark" aria-hidden="true"><Building2 size={20} /></span>
        <span><strong>Prospect</strong><small>CRM commercial</small></span>
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
          <strong>Navigation</strong>
          <button ref={closeButtonRef} type="button" onClick={closeNavigationAndRestoreFocus} aria-label="Fermer la navigation">
            <X size={18} />
          </button>
        </div>
        <nav className="authenticated-navigation" aria-label="Navigation principale">
          {availableRoutes.map((route) => <a
            key={route.id}
            href={route.path}
            aria-current={currentRoute?.id === route.id ? 'page' : undefined}
            onClick={(event) => {
              followInternalLink(event, route.path)
              closeNavigation()
            }}
          >{route.label}</a>)}
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
        <button className="authenticated-logout" type="button" onClick={onLogout} aria-label="Se déconnecter">
          <LogOut size={17} />
        </button>
      </div>
    </header>

    <nav className="route-breadcrumb" aria-label="Fil d’Ariane">
      <span>Prospect CRM</span><span aria-hidden="true">/</span><strong>{currentRoute?.title ?? 'Page introuvable'}</strong>
    </nav>
    <div id="route-content" className="route-content" tabIndex="-1">{children}</div>
  </div>
}
