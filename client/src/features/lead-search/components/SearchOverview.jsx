import { ArrowUpRight, Clock3, Map, UsersRound } from '../../../icons'
import { numberFormatter } from '../config'
import { CoverageMap } from './CoverageMap'


function Metric({ icon, label, value, detail, tone }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-copy"><span>{label}</span><strong>{numberFormatter.format(value)}</strong><small>{detail}</small></div><ArrowUpRight size={17} className="metric-arrow" /></div>
}


export function SearchOverview({ copy, places, result, resultForm, loading, mapEnabled }) {
  return <section className="overview-grid">
    <CoverageMap
      places={places}
      form={resultForm}
      loading={loading}
      searchedAt={result?.searched_at}
      resultToken={result?.map_snapshot_token}
      mapEnabled={mapEnabled}
      copy={copy}
    />
    <div className="metric-stack">
      <Metric icon={<UsersRound />} label={copy.googleResults} value={places.length} detail={copy.maxResults} tone="green" />
      <Metric icon={<Map />} label={copy.searchedArea} value={result ? 1 : 0} detail={copy.radiusDetail.replace('{radius}', resultForm.radius_km)} tone="blue" />
      <Metric icon={<Clock3 />} label={copy.calls} value={result?.stats.api_calls ?? 0} detail={copy.oneTextSearch} tone="gold" />
    </div>
  </section>
}
