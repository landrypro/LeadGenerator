import { useState } from 'react'

import { useBodyScrollLock } from '../../shared/hooks/useBodyScrollLock'
import { useErrorNotice } from '../../shared/hooks/useErrorNotice'
import { Notices } from './components/Notices'
import { ResultsCard } from './components/ResultsCard'
import { SearchOverview } from './components/SearchOverview'
import { SearchSidebar } from './components/SearchSidebar'
import { TopBar } from './components/TopBar'
import { initialForm } from './config'
import { useApiHealth } from './hooks/useApiHealth'
import { useLeadSearch } from './hooks/useLeadSearch'


export function PlaceSearchPage({ session = null, onLogout = null }) {
  const [form, setForm] = useState(initialForm)
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)
  const { error, clearError, reportError } = useErrorNotice()
  const { result, loading, runSearch } = useLeadSearch({ clearError, reportError })
  const keyReady = useApiHealth()

  useBodyScrollLock(mobilePanelOpen)

  const places = result?.places ?? []
  const resultForm = result?.search_parameters ?? form
  const updateForm = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  async function submitSearch(event) {
    event.preventDefault()
    setMobilePanelOpen(false)
    await runSearch(form)
  }

  return <div className="app-shell">
    <SearchSidebar
      form={form}
      loading={loading}
      mobilePanelOpen={mobilePanelOpen}
      onClose={() => setMobilePanelOpen(false)}
      onSubmit={submitSearch}
      onUpdate={updateForm}
    />

    <main className="main-content">
      <TopBar
        keyReady={keyReady}
        mobilePanelOpen={mobilePanelOpen}
        onOpenSettings={() => setMobilePanelOpen(true)}
        session={session}
        onLogout={onLogout}
      />
      <Notices error={error} keyReady={keyReady} onClearError={clearError} />
      <SearchOverview
        places={places}
        result={result}
        resultForm={resultForm}
        loading={loading}
        mapEnabled={session?.capabilities?.includes('google:map') ?? false}
      />
      <ResultsCard
        places={places}
        result={result}
        loading={loading}
      />
      <footer><span>Données temporaires — Google Maps</span><span>•</span><a href="/conditions.html">Conditions d’utilisation</a><span>•</span><a href="/confidentialite.html">Politique de confidentialité</a></footer>
    </main>

  </div>
}
