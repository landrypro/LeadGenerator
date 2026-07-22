import { useMemo, useState } from 'react'

import { Check, Download, LoaderCircle, Phone, Search, X } from '../../../icons'
import { numberFormatter } from '../config'
import { EmptyState, LeadTable, LoadingRows } from './LeadTable'


export function ResultsCard({ leads, result, loading, exporting, onExport }) {
  const [filter, setFilter] = useState('')
  const [contactOnly, setContactOnly] = useState(false)
  const visibleLeads = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    return leads.filter((lead) => {
      const matches = !needle || `${lead.name} ${lead.address} ${lead.phone} ${lead.primary_type}`.toLowerCase().includes(needle)
      return matches && (!contactOnly || lead.phone || lead.website)
    })
  }, [leads, filter, contactOnly])

  return <section className="results-card">
    <div className="results-header">
      <div><p className="eyebrow">Répertoire</p><h2>Entreprises trouvées <span>{numberFormatter.format(leads.length)}</span></h2></div>
      <button className="export-button" disabled={!leads.length || exporting} onClick={onExport}>{exporting ? <LoaderCircle className="spin" size={17} /> : <Download size={17} />} Exporter Excel</button>
    </div>

    <div className="table-tools">
      <div className="table-search"><Search size={16} /><input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filtrer par nom, ville, téléphone…" />{filter && <button onClick={() => setFilter('')}><X size={15} /></button>}</div>
      <button className={`filter-chip ${contactOnly ? 'active' : ''}`} onClick={() => setContactOnly(!contactOnly)}><Phone size={15} /> Avec contact {contactOnly && <Check size={14} />}</button>
      <span className="visible-count">{visibleLeads.length} affiché{visibleLeads.length > 1 ? 's' : ''}</span>
    </div>

    {loading ? <LoadingRows /> : visibleLeads.length ? <LeadTable leads={visibleLeads} /> : <EmptyState hasSearch={!!result} />}
  </section>
}
