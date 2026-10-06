import { useEffect, useRef, useState } from 'react'

import { Menu } from '../../icons'
import { NavigationDialog } from '../../app/NavigationDialog'
import { followInternalLink } from '../../app/navigation'
import { CRM_PATHS } from '../../app/routes'
import { automationApi } from './api/automationApi'


const COPY = {
  'fr-CA': {
    title: 'Automatisation', menu: 'Sections Automatisation', close: 'Fermer les sections Automatisation',
    today: 'Aujourd’hui', playbooks: 'Playbooks', exceptions: 'Entrées et exceptions',
  },
  'en-CA': {
    title: 'Automation', menu: 'Automation sections', close: 'Close Automation sections',
    today: 'Today', playbooks: 'Playbooks', exceptions: 'Entries and exceptions',
  },
}

const SECTIONS = [
  { id: 'today', path: CRM_PATHS.automationToday },
  { id: 'playbooks', path: CRM_PATHS.automationPlaybooks },
  { id: 'exceptions', path: CRM_PATHS.automationExceptions },
]


export function AutomationWorkspace({ activeSection, locale = 'fr-CA', children }) {
  const copy = COPY[locale] ?? COPY['fr-CA']
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false)
  const triggerRef = useRef(null)
  const dialogRef = useRef(null)
  const closeButtonRef = useRef(null)

  function closeMobileNavigation() {
    setMobileNavigationOpen(false)
    requestAnimationFrame(() => triggerRef.current?.focus())
  }

  useEffect(() => {
    if (!mobileNavigationOpen) return undefined
    const closeOnHistoryNavigation = () => closeMobileNavigation()
    window.addEventListener('popstate', closeOnHistoryNavigation)
    return () => window.removeEventListener('popstate', closeOnHistoryNavigation)
  }, [mobileNavigationOpen])

  useEffect(() => {
    const controller = new AbortController()
    // La télémétrie est facultative côté client : elle ne bloque jamais l’ouverture d’une surface.
    const telemetry = automationApi.recordSurfaceOpened?.(activeSection, controller.signal)
    telemetry?.catch(() => {})
    return () => controller.abort()
  }, [activeSection])

  function renderLinks(prefix) {
    return <nav className="automation-section-links" aria-label={copy.title}>
      {SECTIONS.map(section => <a
        key={`${prefix}:${section.id}`}
        href={section.path}
        aria-current={activeSection === section.id ? 'page' : undefined}
        onClick={event => {
          followInternalLink(event, section.path)
          if (event.defaultPrevented) {
            setMobileNavigationOpen(false)
            requestAnimationFrame(() => document.getElementById('route-content')?.focus())
          }
        }}
      >{copy[section.id]}</a>)}
    </nav>
  }

  return <main className="automation-workspace">
    <aside className="automation-section-nav" aria-label={copy.title}>
      <p className="eyebrow">{copy.title}</p>
      {renderLinks('desktop')}
    </aside>
    <div className="automation-mobile-section-nav">
      <button
        ref={triggerRef}
        type="button"
        className="secondary-button"
        aria-expanded={mobileNavigationOpen}
        aria-controls="automation-section-navigation"
        onClick={() => setMobileNavigationOpen(true)}
      ><Menu size={17} />{copy.menu}</button>
    </div>
    <section className="automation-section-content">{children}</section>
    <NavigationDialog
      id="automation-section-navigation"
      className="automation-section-dialog"
      open={mobileNavigationOpen}
      dialogRef={dialogRef}
      closeButtonRef={closeButtonRef}
      title={copy.title}
      closeLabel={copy.close}
      onRequestClose={closeMobileNavigation}
    >{mobileNavigationOpen && renderLinks('mobile')}</NavigationDialog>
  </main>
}
