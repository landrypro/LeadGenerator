import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, ArrowUpRight, Building2, Check, ChevronDown, CircleDollarSign,
  Clock3, Download, ExternalLink, Globe2, Info, LoaderCircle, Map, MapPin,
  Phone, Search, Settings2, Sparkles, Target, UsersRound, X,
} from './icons'

const initialForm = {
  query: 'plombier', center_latitude: 46.8139, center_longitude: -71.2080,
  radius_km: 15, target: 200, max_tiles: 8, max_pages: 3,
  contact_fields: false, include_service_area_businesses: true,
  language_code: 'fr', region_code: 'CA',
}

const number = new Intl.NumberFormat('fr-CA')

function App() {
  const [form, setForm] = useState(initialForm)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  const [keyReady, setKeyReady] = useState(null)
  const [filter, setFilter] = useState('')
  const [contactOnly, setContactOnly] = useState(false)
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)

  useEffect(() => {
    fetch('/api/health').then((r) => r.json()).then((data) => setKeyReady(data.google_api_key_configured)).catch(() => setKeyReady(false))
  }, [])

  useEffect(() => {
    document.body.style.overflow = mobilePanelOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [mobilePanelOpen])

  const leads = result?.leads ?? []
  const visibleLeads = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    return leads.filter((lead) => {
      const matches = !needle || `${lead.name} ${lead.address} ${lead.phone} ${lead.primary_type}`.toLowerCase().includes(needle)
      return matches && (!contactOnly || lead.phone || lead.website)
    })
  }, [leads, filter, contactOnly])

  const projectedCalls = form.max_tiles * form.max_pages
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  async function runSearch(event) {
    event.preventDefault()
    setMobilePanelOpen(false)
    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/leads/search', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'La recherche a échoué.')
      setResult(data)
    } catch (err) {
      setError(err.message || 'Impossible de joindre le serveur.')
    } finally {
      setLoading(false)
    }
  }

  async function exportExcel() {
    if (!leads.length) return
    setExporting(true)
    setError('')
    try {
      const response = await fetch('/api/leads/export', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ leads, search: form }),
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'L’export a échoué.')
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `leads-${form.query.replace(/\s+/g, '-').toLowerCase()}.xlsx`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="app-shell">
      <aside id="search-panel" className={`sidebar ${mobilePanelOpen ? 'mobile-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark"><MapPin size={21} strokeWidth={2.5} /></div>
          <div><strong>Prospect</strong><span>Lead intelligence</span></div>
          <button className="sidebar-close" type="button" onClick={() => setMobilePanelOpen(false)} aria-label="Fermer les paramètres"><X size={19} /></button>
        </div>

        <form onSubmit={runSearch} className="search-form">
          <div className="sidebar-title">
            <span>Nouvelle recherche</span>
            <Settings2 size={17} />
          </div>

          <Field label="Type d’entreprise" hint="Gardez un terme simple, sans ville.">
            <div className="input-with-icon"><Search size={17} /><input value={form.query} onChange={(e) => update('query', e.target.value)} placeholder="Ex. plombier" required /></div>
          </Field>

          <Field label="Centre de la recherche">
            <div className="coordinate-grid">
              <label><span>Latitude</span><input type="number" step="0.0001" min="-90" max="90" value={form.center_latitude} onChange={(e) => update('center_latitude', +e.target.value)} /></label>
              <label><span>Longitude</span><input type="number" step="0.0001" min="-180" max="180" value={form.center_longitude} onChange={(e) => update('center_longitude', +e.target.value)} /></label>
            </div>
          </Field>

          <Field label="Rayon global" value={`${form.radius_km} km`}>
            <input className="range" type="range" min="1" max="50" value={form.radius_km} onChange={(e) => update('radius_km', +e.target.value)} />
            <div className="range-labels"><span>1 km</span><span>50 km</span></div>
          </Field>

          <div className="form-row">
            <Field label="Objectif"><input type="number" min="1" max="500" value={form.target} onChange={(e) => update('target', +e.target.value)} /></Field>
            <Field label="Zones"><input type="number" min="1" max="30" value={form.max_tiles} onChange={(e) => update('max_tiles', +e.target.value)} /></Field>
            <Field label="Pages / zone"><div className="select-wrap"><select value={form.max_pages} onChange={(e) => update('max_pages', +e.target.value)}><option value="1">1</option><option value="2">2</option><option value="3">3</option></select><ChevronDown size={15} /></div></Field>
          </div>

          <Toggle checked={form.contact_fields} onChange={(value) => update('contact_fields', value)} title="Téléphone et site Web" description="Champs de contact facturés à un niveau supérieur" accent />
          <Toggle checked={form.include_service_area_businesses} onChange={(value) => update('include_service_area_businesses', value)} title="Entreprises de zone de service" description="Inclure celles qui n’affichent pas d’adresse" />

          <div className="call-estimate"><CircleDollarSign size={18} /><div><strong>Jusqu’à {projectedCalls} appels API</strong><span>{form.contact_fields ? 'Champs de contact activés' : 'Mode économique sans contacts'}</span></div></div>

          <button className="primary-button" disabled={loading || !form.query.trim()}>
            {loading ? <><LoaderCircle className="spin" size={18} /> Recherche en cours…</> : <><Sparkles size={18} /> Générer les leads</>}
          </button>
          <p className="form-footnote"><Info size={14} /> Objectif d’arrêt, sans garantie d’exhaustivité.</p>
        </form>
      </aside>
      {mobilePanelOpen && <button className="mobile-backdrop" type="button" onClick={() => setMobilePanelOpen(false)} aria-label="Fermer le panneau de recherche" />}

      <main className="main-content">
        <header className="topbar">
          <div className="topbar-heading">
            <button className="mobile-controls-button" type="button" onClick={() => setMobilePanelOpen(true)} aria-expanded={mobilePanelOpen} aria-controls="search-panel" aria-label="Ouvrir les paramètres de recherche"><Settings2 size={17} /><span>Paramètres</span></button>
            <div><p className="eyebrow">Google Places API (New)</p><h1>Générateur de leads locaux</h1></div>
          </div>
          <div className={`api-status ${keyReady ? 'ready' : ''}`} title={keyReady ? 'API configurée' : 'Clé API absente'}><span />{keyReady === null ? 'Vérification…' : keyReady ? 'API configurée' : 'Clé API absente'}</div>
        </header>

        {error && <div className="error-banner"><AlertTriangle size={19} /><span>{error}</span><button onClick={() => setError('')} aria-label="Fermer"><X size={17} /></button></div>}
        {keyReady === false && <div className="setup-banner"><div className="setup-icon"><Info size={20} /></div><div><strong>Une étape avant la première recherche</strong><p>Ajoutez <code>GOOGLE_MAPS_API_KEY</code> aux variables d’environnement du serveur, puis relancez l’API.</p></div></div>}

        <section className="overview-grid">
          <CoverageMap leads={leads} form={form} loading={loading} />
          <div className="metric-stack">
            <Metric icon={<UsersRound />} label="Leads uniques" value={leads.length} detail={result?.stats.target_reached ? 'Objectif atteint' : `sur ${form.target} visés`} tone="green" />
            <Metric icon={<Map />} label="Zones explorées" value={result?.stats.zones_searched ?? 0} detail={`sur ${form.max_tiles} configurées`} tone="blue" />
            <Metric icon={<Clock3 />} label="Appels effectués" value={result?.stats.api_calls ?? 0} detail={`${result?.stats.duplicates_removed ?? 0} doublons retirés`} tone="gold" />
          </div>
        </section>

        <section className="results-card">
          <div className="results-header">
            <div><p className="eyebrow">Répertoire</p><h2>Entreprises trouvées <span>{number.format(leads.length)}</span></h2></div>
            <button className="export-button" disabled={!leads.length || exporting} onClick={exportExcel}>{exporting ? <LoaderCircle className="spin" size={17} /> : <Download size={17} />} Exporter Excel</button>
          </div>

          <div className="table-tools">
            <div className="table-search"><Search size={16} /><input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filtrer par nom, ville, téléphone…" />{filter && <button onClick={() => setFilter('')}><X size={15} /></button>}</div>
            <button className={`filter-chip ${contactOnly ? 'active' : ''}`} onClick={() => setContactOnly(!contactOnly)}><Phone size={15} /> Avec contact {contactOnly && <Check size={14} />}</button>
            <span className="visible-count">{visibleLeads.length} affiché{visibleLeads.length > 1 ? 's' : ''}</span>
          </div>

          {loading ? <LoadingRows /> : visibleLeads.length ? <LeadTable leads={visibleLeads} /> : <EmptyState hasSearch={!!result} />}
        </section>
        <footer><span>Données fournies par Google Places</span><span>•</span><span>Respectez les conditions Google Maps Platform et les lois de prospection applicables.</span></footer>
      </main>
    </div>
  )
}

function Field({ label, value, hint, children }) {
  return <div className="field"><div className="field-label"><label>{label}</label>{value && <strong>{value}</strong>}</div>{children}{hint && <small>{hint}</small>}</div>
}

function Toggle({ checked, onChange, title, description, accent }) {
  return <label className={`toggle-row ${accent ? 'accent' : ''}`}><div><strong>{title}</strong><span>{description}</span></div><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} /><i><b /></i></label>
}

function Metric({ icon, label, value, detail, tone }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-copy"><span>{label}</span><strong>{number.format(value)}</strong><small>{detail}</small></div><ArrowUpRight size={17} className="metric-arrow" /></div>
}

function CoverageMap({ leads, form, loading }) {
  const pins = leads.filter((lead) => lead.latitude != null).slice(0, 40).map((lead) => {
    const dx = (lead.longitude - form.center_longitude) * 111 * Math.cos(form.center_latitude * Math.PI / 180)
    const dy = (lead.latitude - form.center_latitude) * 111
    return { ...lead, x: Math.max(5, Math.min(95, 50 + (dx / form.radius_km) * 45)), y: Math.max(5, Math.min(95, 50 - (dy / form.radius_km) * 45)) }
  })
  return <div className="coverage-card">
    <div className="map-top"><div><p className="eyebrow">Aperçu de couverture</p><h2>Rayon de {form.radius_km} km</h2></div><div className="zone-pill"><Target size={14} /> {form.max_tiles} zones</div></div>
    <div className="map-canvas">
      <div className="map-road road-one" /><div className="map-road road-two" /><div className="map-road road-three" />
      <div className="radius-ring ring-one" /><div className="radius-ring ring-two" /><div className="center-marker"><MapPin size={17} fill="currentColor" /></div>
      {pins.map((pin, index) => <span key={`${pin.place_id}-${index}`} className="lead-pin" title={pin.name} style={{ left: `${pin.x}%`, top: `${pin.y}%`, animationDelay: `${index * 18}ms` }} />)}
      {!pins.length && !loading && <div className="map-empty"><MapPin size={22} /><span>Les résultats apparaîtront ici</span></div>}
      {loading && <div className="scan"><span /></div>}
      <div className="map-legend"><i /> Centre <b /> Lead</div>
    </div>
  </div>
}

function LeadTable({ leads }) {
  return <div className="table-wrap"><table><thead><tr><th>Entreprise</th><th>Contact</th><th>Localisation</th><th>Distance</th><th>Statut</th><th><span className="sr-only">Ouvrir</span></th></tr></thead><tbody>
    {leads.map((lead, index) => <tr key={lead.place_id || `${lead.name}-${index}`}>
      <td><div className="company-cell"><div className="company-avatar">{lead.name?.slice(0, 1).toUpperCase() || <Building2 size={16} />}</div><div><strong>{lead.name || 'Sans nom'}</strong><span>{formatType(lead.primary_type)}</span></div></div></td>
      <td><div className="contact-cell">{lead.phone ? <a href={`tel:${lead.phone}`}><Phone size={14} />{lead.phone}</a> : <span className="muted">Téléphone non demandé</span>}{lead.website && <a href={lead.website} target="_blank" rel="noreferrer"><Globe2 size={14} />Site Web</a>}</div></td>
      <td><div className="address-cell"><MapPin size={15} /><span>{lead.address || 'Zone de service — adresse masquée'}</span></div></td>
      <td>{lead.radius_verified ? <span className="distance">{lead.distance_km?.toLocaleString('fr-CA')} km</span> : <span className="unverified">Non vérifiable</span>}</td>
      <td><span className={`status-badge ${lead.business_status === 'OPERATIONAL' ? 'active' : ''}`}><i />{lead.business_status === 'OPERATIONAL' ? 'Ouvert' : lead.business_status || 'Inconnu'}</span></td>
      <td>{lead.google_maps_url && <a className="open-link" href={lead.google_maps_url} target="_blank" rel="noreferrer" aria-label={`Ouvrir ${lead.name} dans Google Maps`}><ExternalLink size={16} /></a>}</td>
    </tr>)}
  </tbody></table></div>
}

function formatType(value) { return value ? value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase()) : 'Entreprise locale' }

function EmptyState({ hasSearch }) {
  return <div className="empty-state"><div className="empty-illustration"><Search size={26} /><span /><i /></div><h3>{hasSearch ? 'Aucun résultat pour ce filtre' : 'Prêt à trouver vos prochains clients'}</h3><p>{hasSearch ? 'Modifiez les filtres pour afficher davantage d’entreprises.' : 'Configurez votre zone et lancez une première recherche. Commencez petit pour maîtriser les coûts.'}</p></div>
}

function LoadingRows() {
  return <div className="loading-rows">{[1, 2, 3, 4].map((row) => <div className="loading-row" key={row}><i /><span /><span /><span /></div>)}</div>
}

export default App
