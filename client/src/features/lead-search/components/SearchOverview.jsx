import { ArrowUpRight, Clock3, Map, UsersRound } from '../../../icons'
import { numberFormatter } from '../config'
import { CoverageMap } from './CoverageMap'


function Metric({ icon, label, value, detail, tone }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-copy"><span>{label}</span><strong>{numberFormatter.format(value)}</strong><small>{detail}</small></div><ArrowUpRight size={17} className="metric-arrow" /></div>
}


export function SearchOverview({ places, result, resultForm, loading }) {
  return <section className="overview-grid">
    <CoverageMap
      places={places}
      form={resultForm}
      loading={loading}
      searchedAt={result?.searched_at}
      resultToken={result?.map_snapshot_token}
    />
    <div className="metric-stack">
      <Metric icon={<UsersRound />} label="Résultats Google" value={places.length} detail="20 maximum par recherche" tone="green" />
      <Metric icon={<Map />} label="Zone interrogée" value={result ? 1 : 0} detail={`rayon de ${resultForm.radius_km} km`} tone="blue" />
      <Metric icon={<Clock3 />} label="Appels effectués" value={result?.stats.api_calls ?? 0} detail="un seul appel Text Search" tone="gold" />
    </div>
  </section>
}
