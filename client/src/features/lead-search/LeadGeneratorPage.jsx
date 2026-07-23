import { useCallback, useState } from 'react'

import { useBodyScrollLock } from '../../shared/hooks/useBodyScrollLock'
import { useErrorNotice } from '../../shared/hooks/useErrorNotice'
import { useEscapeKey } from '../../shared/hooks/useEscapeKey'
import { IdentityModal } from './components/IdentityModal'
import { Notices } from './components/Notices'
import { ResultsCard } from './components/ResultsCard'
import { SearchOverview } from './components/SearchOverview'
import { SearchSidebar } from './components/SearchSidebar'
import { TopBar } from './components/TopBar'
import { initialForm, initialRequester } from './config'
import { useApiHealth } from './hooks/useApiHealth'
import { useLeadSearch } from './hooks/useLeadSearch'


export function PlaceSearchPage({ session = null, onLogout = null }) {
  const [form, setForm] = useState(initialForm)
  const [requester, setRequester] = useState(initialRequester)
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)
  const [identityModalOpen, setIdentityModalOpen] = useState(false)
  const { error, clearError, reportError } = useErrorNotice()
  const { result, loading, runSearch } = useLeadSearch({ clearError, reportError })
  const keyReady = useApiHealth()

  useBodyScrollLock(mobilePanelOpen || identityModalOpen)
  const closeIdentityModal = useCallback(() => setIdentityModalOpen(false), [])
  useEscapeKey(identityModalOpen && !loading, closeIdentityModal)

  const places = result?.places ?? []
  const resultForm = result?.search_parameters ?? form
  const updateForm = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  function requestGeneration(event) {
    event.preventDefault()
    setMobilePanelOpen(false)
    setIdentityModalOpen(true)
  }

  async function confirmGeneration(event) {
    event.preventDefault()
    setIdentityModalOpen(false)
    await runSearch(form, requester)
  }

  return <div className="app-shell">
    <SearchSidebar
      form={form}
      loading={loading}
      mobilePanelOpen={mobilePanelOpen}
      onClose={() => setMobilePanelOpen(false)}
      onSubmit={requestGeneration}
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
      <SearchOverview places={places} result={result} resultForm={resultForm} loading={loading} />
      <ResultsCard
        places={places}
        result={result}
        loading={loading}
      />
      <footer><span>Données temporaires — Google Maps</span><span>•</span><a href="/conditions.html">Conditions d’utilisation</a><span>•</span><a href="/confidentialite.html">Politique de confidentialité</a></footer>
    </main>

    {identityModalOpen && <IdentityModal requester={requester} setRequester={setRequester} onClose={closeIdentityModal} onConfirm={confirmGeneration} />}
  </div>
}
