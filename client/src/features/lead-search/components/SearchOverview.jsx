import { ArrowUpRight, Clock3, Map, UsersRound } from '../../../icons'
import { numberFormatter } from '../config'
import { CoverageMap } from './CoverageMap'


function Metric({ icon, label, value, detail, tone }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-copy"><span>{label}</span><strong>{numberFormatter.format(value)}</strong><small>{detail}</small></div><ArrowUpRight size={17} className="metric-arrow" /></div>
}


export function SearchOverview({ leads, result, resultForm, loading }) {
  return <section className="overview-grid">
    <CoverageMap
      leads={leads}
      form={resultForm}
      loading={loading}
      generatedAt={result?.generated_at}
      resultToken={result?.map_snapshot_token}
    />
    <div className="metric-stack">
      <Metric icon={<UsersRound />} label="Leads uniques" value={leads.length} detail={result?.stats.target_reached ? 'Objectif atteint' : `sur ${resultForm.target} visés`} tone="green" />
      <Metric icon={<Map />} label="Zones explorées" value={result?.stats.zones_searched ?? 0} detail={`sur ${resultForm.max_tiles} configurées`} tone="blue" />
      <Metric icon={<Clock3 />} label="Appels effectués" value={result?.stats.api_calls ?? 0} detail={`${result?.stats.duplicates_removed ?? 0} doublons retirés`} tone="gold" />
    </div>
  </section>
}
