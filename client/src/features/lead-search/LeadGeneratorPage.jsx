// Orchestrateur de la recherche : les composants enfants affichent l’UI, tandis
// que cette page possède l’état partagé du formulaire, des résultats et de la carte.
import { useEffect, useRef, useState } from 'react'

import { useBodyScrollLock } from '../../shared/hooks/useBodyScrollLock'
import { useErrorNotice } from '../../shared/hooks/useErrorNotice'
import { MobileSearchSummary } from './components/MobileSearchSummary'
import { Notices } from './components/Notices'
import { ResultsCard } from './components/ResultsCard'
import { SearchOverview } from './components/SearchOverview'
import { SearchSidebar } from './components/SearchSidebar'
import { TopBar } from './components/TopBar'
import { initialForm } from './config'
import { useApiHealth } from './hooks/useApiHealth'
import { useLeadSearch } from './hooks/useLeadSearch'
import { useProspectAdds } from './hooks/useProspectAdds'
import { leadSearchMessages } from './messages'


const SEARCH_SETTINGS_HISTORY_KEY = '__marketteoSearchSettingsOverlay'

function createInitialLocation() {
  return { area: '', locality: '', areaCountry: '', areaSelected: false, localitySelected: false }
}

function cloneSearchForm(form) {
  return { ...form }
}

function cloneLocation(location) {
  return { ...location }
}

function stateWithoutSearchSettingsMarker(state) {
  if (!state || typeof state !== 'object') return {}
  const { [SEARCH_SETTINGS_HISTORY_KEY]: _ignored, ...rest } = state
  return rest
}

export function PlaceSearchPage({ session = null }) {
  const locale = session?.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = leadSearchMessages[locale]
  const [form, setForm] = useState(() => cloneSearchForm(initialForm))
  const [location, setLocation] = useState(createInitialLocation)
  const [manualMode, setManualMode] = useState(false)
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)
  const [appliedSearch, setAppliedSearch] = useState(null)
  const [mobileMapExpanded, setMobileMapExpanded] = useState(false)
  const settingsTriggerRef = useRef(null)
  const panelOpenRef = useRef(false)
  const previousOrganizationRef = useRef(session?.active_organization?.id ?? '')
  const { error, clearError, reportError } = useErrorNotice()
  const { result, loading, runSearch, clearSearch } = useLeadSearch({ clearError, reportError })
  const prospectAdds = useProspectAdds({
    selectionToken: result?.selection_token ?? '',
    clearError,
    reportError,
  })
  const keyReady = useApiHealth()
  const activeOrganizationId = session?.active_organization?.id ?? ''

  panelOpenRef.current = mobilePanelOpen
  useBodyScrollLock(mobilePanelOpen)

  const places = result?.places ?? []
  const resultForm = appliedSearch?.form ?? result?.search_parameters ?? form

  function restoreSettingsTriggerFocus() {
    requestAnimationFrame(() => settingsTriggerRef.current?.focus())
  }

  function discardSearchSettingsHistoryMarker() {
    if (!window.history.state?.[SEARCH_SETTINGS_HISTORY_KEY]) return
    window.history.replaceState(stateWithoutSearchSettingsMarker(window.history.state), '')
  }

  function openSearchSettings(event) {
    settingsTriggerRef.current = event?.currentTarget ?? settingsTriggerRef.current
    if (!window.history.state?.[SEARCH_SETTINGS_HISTORY_KEY]) {
      window.history.pushState({ ...(window.history.state ?? {}), [SEARCH_SETTINGS_HISTORY_KEY]: true }, '')
    }
    setMobilePanelOpen(true)
  }

  function requestSearchSettingsClose() {
    // Le marqueur History permet au bouton Retour de fermer le panneau mobile
    // sans quitter la page de recherche.
    const consumedHistoryEntry = Boolean(window.history.state?.[SEARCH_SETTINGS_HISTORY_KEY])
    setMobilePanelOpen(false)
    restoreSettingsTriggerFocus()
    if (consumedHistoryEntry) window.history.back()
  }

  function cancelSearchSettings() {
    if (appliedSearch) {
      setForm(cloneSearchForm(appliedSearch.form))
      setLocation(cloneLocation(appliedSearch.location))
      setManualMode(appliedSearch.manualMode)
    } else {
      setForm(cloneSearchForm(initialForm))
      setLocation(createInitialLocation())
      setManualMode(false)
    }
    requestSearchSettingsClose()
  }

  useEffect(() => {
    const closeOnHistoryNavigation = () => {
      if (!panelOpenRef.current) return
      setMobilePanelOpen(false)
      restoreSettingsTriggerFocus()
    }
    window.addEventListener('popstate', closeOnHistoryNavigation)
    return () => window.removeEventListener('popstate', closeOnHistoryNavigation)
  }, [])

  useEffect(() => {
    if (!mobilePanelOpen || typeof window.matchMedia !== 'function') return undefined
    const desktop = window.matchMedia('(min-width: 761px)')
    const closeWhenDesktopReturns = event => {
      if (!event.matches) return
      discardSearchSettingsHistoryMarker()
      setMobilePanelOpen(false)
      restoreSettingsTriggerFocus()
    }
    desktop.addEventListener?.('change', closeWhenDesktopReturns)
    return () => desktop.removeEventListener?.('change', closeWhenDesktopReturns)
  }, [mobilePanelOpen])

  useEffect(() => {
    if (previousOrganizationRef.current === activeOrganizationId) return
    previousOrganizationRef.current = activeOrganizationId
    discardSearchSettingsHistoryMarker()
    setMobilePanelOpen(false)
    setMobileMapExpanded(false)
    setAppliedSearch(null)
    setForm(cloneSearchForm(initialForm))
    setLocation(createInitialLocation())
    setManualMode(false)
    clearSearch()
    clearError()
  }, [activeOrganizationId, clearError, clearSearch])

  const updateForm = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }))
    if (key === 'center_latitude' || key === 'center_longitude') {
      setLocation((current) => ({ ...current, locality: '', localitySelected: false }))
    }
  }
  const updateLocation = (key, value) => setLocation((current) => ({
    ...current, [key]: value,
    ...(key === 'area' ? { areaCountry: '', areaSelected: false, locality: '', localitySelected: false } : { localitySelected: false }),
  }))
  const selectLocation = (key, value) => {
    setLocation((current) => key === 'area'
      ? { area: value.label, areaCountry: value.region_code, areaSelected: true, locality: '', localitySelected: false }
      : { ...current, locality: value.label, localitySelected: true })
    if (key === 'locality') setForm((current) => ({
      ...current, center_latitude: value.latitude, center_longitude: value.longitude,
      region_code: value.region_code || current.region_code,
    }))
  }

  async function submitSearch(event) {
    event.preventDefault()
    if (!manualMode && !(location.areaSelected && location.localitySelected)) return
    const submittedForm = cloneSearchForm(form)
    const submittedLocation = cloneLocation(location)
    const submittedManualMode = manualMode
    discardSearchSettingsHistoryMarker()
    setMobilePanelOpen(false)
    const data = await runSearch({ ...submittedForm, language_code: locale === 'en-CA' ? 'en' : 'fr' })
    if (!data) return
    setAppliedSearch({
      form: { ...submittedForm, ...(data.search_parameters ?? {}) },
      location: submittedLocation,
      manualMode: submittedManualMode,
    })
    setMobileMapExpanded(false)
    requestAnimationFrame(() => document.getElementById('search-results-heading')?.focus())
  }

  return <div className="app-shell">
    <SearchSidebar
      appliedSearch={appliedSearch}
      form={form}
      loading={loading}
      mobilePanelOpen={mobilePanelOpen}
      onCancel={cancelSearchSettings}
      onClose={requestSearchSettingsClose}
      onSubmit={submitSearch}
      onUpdate={updateForm}
      copy={copy}
      locale={locale}
      location={location}
      onLocationChange={updateLocation}
      onLocationSelect={selectLocation}
      manualMode={manualMode}
      onManualMode={setManualMode}
    />

    <main className="main-content" inert={mobilePanelOpen || undefined}>
      <TopBar
        keyReady={keyReady}
        mobilePanelOpen={mobilePanelOpen}
        onOpenSettings={openSearchSettings}
        settingsButtonRef={settingsTriggerRef}
        copy={copy}
      />
      <Notices error={error} keyReady={keyReady} onClearError={clearError} copy={copy} />
      <MobileSearchSummary
        copy={copy}
        appliedSearch={appliedSearch}
        mapExpanded={mobileMapExpanded}
        onEdit={openSearchSettings}
        onToggleMap={() => setMobileMapExpanded((current) => !current)}
      />
      <div className={`search-workspace ${result ? 'has-search' : ''} ${mobileMapExpanded ? 'mobile-map-expanded' : ''}`}>
        <SearchOverview
          places={places}
          result={result}
          resultForm={resultForm}
          loading={loading}
          mapEnabled={session?.capabilities?.includes('google:map') ?? false}
          copy={copy}
        />
        <ResultsCard
          places={places}
          result={result}
          loading={loading}
          canCreateProspects={session?.capabilities?.includes('prospects:create') ?? false}
          prospectAdds={prospectAdds}
          copy={copy}
        />
      </div>
      <footer><span>{copy.footerData}</span><span>•</span><a href="/conditions.html">{copy.terms}</a><span>•</span><a href="/confidentialite.html">{copy.privacy}</a></footer>
    </main>

  </div>
}
