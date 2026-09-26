import { useEffect, useRef, useState } from 'react'

import { Building2, ExternalLink, LogOut, Menu } from '../icons'
import { OrganizationSwitcher } from '../features/organizations/OrganizationSwitcher'
import { followInternalLink, navigate } from './navigation'
import { CRM_PATHS, localizedRouteLabel, localizedRouteTitle, navigationRoutes } from './routes'
import { navigationLabel, navigationModel, navigationRouteId } from './navigationModel'
import { MobileNavigationBar } from './MobileNavigationBar'
import { NavigationDialog } from './NavigationDialog'
import { NavigationDisclosure } from './NavigationDisclosure'
import './navigation.css'
import { resolvePublicLocale } from './publicLocale'


const NAVIGATION_HISTORY_KEY = '__marketteoNavigationOverlay'

function ordinaryPrimaryClick(event) {
  return event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey
}

function stateWithoutNavigationMarker(state) {
  if (!state || typeof state !== 'object') return {}
  const { [NAVIGATION_HISTORY_KEY]: _ignored, ...rest } = state
  return rest
}

export function AuthenticatedLayout({
  children,
  currentRoute,
  session,
  onLogout,
  onSwitchOrganization,
  switchingOrganization = false,
}) {
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false)
  const appRef = useRef(null)
  const menuButtonRef = useRef(null)
  const dialogRef = useRef(null)
  const closeButtonRef = useRef(null)
  const navigationTriggerRef = useRef(null)
  const navigationOpenRef = useRef(false)
  const availableRoutes = navigationRoutes(session)
  const locale = session.active_organization?.locale ?? resolvePublicLocale()
  const model = navigationModel(session, locale)
  const activeNavigationId = navigationRouteId(currentRoute)
  const contextKey = `${session.user.id}:${session.active_organization?.id ?? 'none'}:${locale}:${session.capabilities.join(',')}:${currentRoute?.id}`
  const previousContextKeyRef = useRef(contextKey)
  const membership = session.memberships.find(item => item.organization.id === session.active_organization?.id)
  const role = membership?.role ?? session.user.platform_role
  const roleLabels = locale === 'en-CA' ? { admin: 'Administrator', manager: 'Manager', sales: 'Sales', platform_admin: 'Platform administrator' } : { admin: 'Administrateur', manager: 'Gestionnaire', sales: 'Commercial', platform_admin: 'Administrateur de plateforme' }
  const copy = locale === 'en-CA'
    ? { skip: 'Skip to main content', home: 'Marketteo CRM — Home', crm: 'Sales CRM', menu: 'Menu', navigation: 'Navigation', closeNavigation: 'Close navigation', mainNavigation: 'Main navigation', manual: 'Manual', signOut: 'Sign out', breadcrumb: 'Breadcrumb' }
    : { skip: 'Aller au contenu principal', home: 'Marketteo CRM — Accueil', crm: 'CRM commercial', menu: 'Menu', navigation: 'Navigation', closeNavigation: 'Fermer la navigation', mainNavigation: 'Navigation principale', manual: 'Manuel', signOut: 'Se déconnecter', breadcrumb: 'Fil d’Ariane' }

  navigationOpenRef.current = mobileNavigationOpen

  function restoreNavigationTriggerFocus() {
    requestAnimationFrame(() => navigationTriggerRef.current?.focus())
  }

  function discardNavigationHistoryMarker() {
    if (!window.history.state?.[NAVIGATION_HISTORY_KEY]) return
    window.history.replaceState(stateWithoutNavigationMarker(window.history.state), '')
  }

  function openNavigation(event) {
    navigationTriggerRef.current = event.currentTarget
    if (!window.history.state?.[NAVIGATION_HISTORY_KEY]) {
      window.history.pushState({ ...(window.history.state ?? {}), [NAVIGATION_HISTORY_KEY]: true }, '')
    }
    setMobileNavigationOpen(true)
  }

  function requestNavigationClose() {
    const consumedHistoryEntry = Boolean(window.history.state?.[NAVIGATION_HISTORY_KEY])
    setMobileNavigationOpen(false)
    restoreNavigationTriggerFocus()
    if (consumedHistoryEntry) window.history.back()
  }

  useEffect(() => {
    const closeOnHistoryNavigation = () => {
      if (!navigationOpenRef.current) return
      setMobileNavigationOpen(false)
      restoreNavigationTriggerFocus()
    }
    window.addEventListener('popstate', closeOnHistoryNavigation)
    return () => window.removeEventListener('popstate', closeOnHistoryNavigation)
  }, [])

  useEffect(() => {
    if (!mobileNavigationOpen || typeof window.matchMedia !== 'function') return undefined
    const desktop = window.matchMedia('(min-width: 1400px)')
    const closeWhenDesktopReturns = event => {
      if (!event.matches) return
      discardNavigationHistoryMarker()
      setMobileNavigationOpen(false)
      restoreNavigationTriggerFocus()
    }
    desktop.addEventListener?.('change', closeWhenDesktopReturns)
    return () => desktop.removeEventListener?.('change', closeWhenDesktopReturns)
  }, [mobileNavigationOpen])

  useEffect(() => {
    if (previousContextKeyRef.current !== contextKey && navigationOpenRef.current) {
      discardNavigationHistoryMarker()
      setMobileNavigationOpen(false)
    }
    previousContextKeyRef.current = contextKey
  }, [contextKey]) // A route, locale, organization or capability change invalidates the open menu.

  function navigateToRoute(event, route) {
    if (navigationOpenRef.current && ordinaryPrimaryClick(event)) {
      event.preventDefault()
      discardNavigationHistoryMarker()
      navigate(route.path, { replace: true })
    } else {
      followInternalLink(event, route.path)
    }
    if (!event.defaultPrevented) return
    setMobileNavigationOpen(false)
    requestAnimationFrame(() => document.getElementById('route-content')?.focus())
  }

  function routeLink(route, keyPrefix = 'desktop') {
    return <a key={`${keyPrefix}:${route.id}`} href={route.path}
      aria-current={activeNavigationId === route.id ? 'page' : undefined}
      onClick={event => navigateToRoute(event, route)}>{navigationLabel(route, locale) ?? localizedRouteLabel(route, locale)}</a>
  }

  function navigationContent(keyPrefix) {
    return <nav className="authenticated-navigation" aria-label={copy.mainNavigation}>
      {model.direct.map(route => routeLink(route, keyPrefix))}
      {model.groups.map(group => <NavigationDisclosure key={`${contextKey}:${keyPrefix}:${group.id}`} label={group.label}
        active={group.routes.some(route => route.id === activeNavigationId)}>
        {group.routes.map(route => routeLink(route, keyPrefix))}
      </NavigationDisclosure>)}
    </nav>
  }

  function closeDisclosuresOutside(event) {
    appRef.current?.querySelectorAll('.navigation-disclosure[open]').forEach(disclosure => {
      if (!disclosure.contains(event.target)) disclosure.removeAttribute('open')
    })
  }

  const homePath = model.direct[0]?.path ?? availableRoutes[0]?.path ?? CRM_PATHS.account

  return <div ref={appRef} className="authenticated-app" onPointerDownCapture={closeDisclosuresOutside} onFocusCapture={closeDisclosuresOutside}>
    <a className="skip-link" href="#route-content">{copy.skip}</a>
    <header className="authenticated-header">
      <a
        className="authenticated-brand"
        href={homePath}
        onClick={(event) => followInternalLink(event, homePath)}
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
        onClick={openNavigation}
      >
        <Menu size={19} /><span>{copy.menu}</span>
      </button>

      <div className="authenticated-desktop-navigation">{navigationContent('desktop')}</div>

      <div className="authenticated-context">
        <OrganizationSwitcher
          session={session}
          switching={switchingOrganization}
          onSwitch={onSwitchOrganization}
        />
        <a
          className="authenticated-manual-link"
          href="/manuel-utilisateur/index.html"
          target="_blank"
          rel="noopener noreferrer"
        ><ExternalLink size={15} /><span>{copy.manual}</span></a>
        <NavigationDisclosure key={`${contextKey}:user`} className="authenticated-account-menu"
          label={session.user.display_name} active={currentRoute?.id === 'account'}>
          {role && <span className="authenticated-account-role">{roleLabels[role] ?? role}</span>}
          {model.account && routeLink(model.account, 'account')}
          <button type="button" onClick={onLogout}><LogOut size={17} />{copy.signOut}</button>
        </NavigationDisclosure>
      </div>
    </header>

    <NavigationDialog
      open={mobileNavigationOpen}
      dialogRef={dialogRef}
      closeButtonRef={closeButtonRef}
      title={copy.navigation}
      closeLabel={copy.closeNavigation}
      onRequestClose={requestNavigationClose}
      footer={<a href="/manuel-utilisateur/index.html" target="_blank" rel="noopener noreferrer"><ExternalLink size={16} />{copy.manual}</a>}
    >
      {mobileNavigationOpen && navigationContent('dialog')}
    </NavigationDialog>

    <nav className="route-breadcrumb" aria-label={copy.breadcrumb}>
      <span>Marketteo CRM</span><span aria-hidden="true">/</span><strong>{localizedRouteTitle(currentRoute, locale) || (locale === 'en-CA' ? 'Page not found' : 'Page introuvable')}</strong>
    </nav>
    <div id="route-content" className="route-content" tabIndex="-1">{children}</div>

    <MobileNavigationBar
      routes={model.mobile}
      activeId={activeNavigationId}
      locale={locale}
      navigationOpen={mobileNavigationOpen}
      onNavigate={navigateToRoute}
      onOpenNavigation={openNavigation}
    />
  </div>
}
