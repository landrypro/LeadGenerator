import { AuditFilters } from './components/AuditFilters'
import { AuditTimeline } from './components/AuditTimeline'
import { PLATFORM_ACTIONS } from './catalog'
import { useAuditEvents } from './hooks/useAuditEvents'
import { AuditHeading } from './TenantAuditPage'


export function PlatformAuditPage({ session }) {
  const audit = useAuditEvents('platform')
  const actors = [{ id: session.user.id, displayName: `${session.user.display_name} (moi)` }]
  return <main className="administration-page audit-page platform-page" aria-labelledby="platform-audit-title">
    <AuditHeading
      eyebrow="Administration de la plateforme"
      id="platform-audit-title"
      title="Audit plateforme"
      description="Consultez uniquement les opérations de portée plateforme. Les données locataires restent séparées."
    />
    <AuditFilters actions={PLATFORM_ACTIONS} actors={actors} filters={audit.filters} onApply={audit.applyFilters} onReset={audit.resetFilters} />
    <AuditTimeline audit={audit} timezone="UTC" />
  </main>
}
