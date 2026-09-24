import { useState } from 'react'

import { useBodyScrollLock } from '../../shared/hooks/useBodyScrollLock'
import { useErrorNotice } from '../../shared/hooks/useErrorNotice'
import { Notices } from './components/Notices'
import { ResultsCard } from './components/ResultsCard'
import { SearchOverview } from './components/SearchOverview'
import { SearchSidebar } from './components/SearchSidebar'
import { TopBar } from './components/TopBar'
import { initialForm } from './config'
import { leadSearchMessages } from './messages'
import { useApiHealth } from './hooks/useApiHealth'
import { useLeadSearch } from './hooks/useLeadSearch'
import { useProspectAdds } from './hooks/useProspectAdds'


export function PlaceSearchPage({ session = null }) {
  const locale = session?.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = leadSearchMessages[locale]
  const [form, setForm] = useState(initialForm)
  const [location, setLocation] = useState({ area: '', locality: '', areaCountry: '', areaSelected: false, localitySelected: false })
  const [manualMode, setManualMode] = useState(false)
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)
  const { error, clearError, reportError } = useErrorNotice()
  const { result, loading, runSearch } = useLeadSearch({ clearError, reportError })
  const prospectAdds = useProspectAdds({
    selectionToken: result?.selection_token ?? '',
    clearError,
    reportError,
  })
  const keyReady = useApiHealth()

  useBodyScrollLock(mobilePanelOpen)

  const places = result?.places ?? []
  const resultForm = result?.search_parameters ?? form
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
    setMobilePanelOpen(false)
    if (!manualMode && !(location.areaSelected && location.localitySelected)) return
    await runSearch({ ...form, language_code: locale === 'en-CA' ? 'en' : 'fr' })
  }

  return <div className="app-shell">
    <SearchSidebar
      form={form}
      loading={loading}
      mobilePanelOpen={mobilePanelOpen}
      onClose={() => setMobilePanelOpen(false)}
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

    <main className="main-content">
      <TopBar
        keyReady={keyReady}
        mobilePanelOpen={mobilePanelOpen}
        onOpenSettings={() => setMobilePanelOpen(true)}
        copy={copy}
      />
      <Notices error={error} keyReady={keyReady} onClearError={clearError} copy={copy} />
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
      <footer><span>{copy.footerData}</span><span>•</span><a href="/conditions.html">{copy.terms}</a><span>•</span><a href="/confidentialite.html">{copy.privacy}</a></footer>
    </main>

  </div>
}
