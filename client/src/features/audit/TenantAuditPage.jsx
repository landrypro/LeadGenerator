import { Clock3 } from '../../icons'
import { useMembers } from '../organizations/hooks/useMembers'
import { useOrganization } from '../organizations/hooks/useOrganization'
import { AuditFilters } from './components/AuditFilters'
import { AuditTimeline } from './components/AuditTimeline'
import { tenantActions } from './catalog'
import { useAuditEvents } from './hooks/useAuditEvents'


export function TenantAuditPage({ session }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = locale === 'en-CA' ? { eyebrow: 'Administration', title: 'Activity log', description: `Review confirmed changes for ${session.active_organization?.name ?? 'the active organization'}.` } : { eyebrow: 'Administration', title: 'Journal d’activité', description: `Consultez les changements validés de ${session.active_organization?.name ?? 'l’organisation active'}.` }
  const audit = useAuditEvents('tenant')
  const members = useMembers()
  const organization = useOrganization()
  const actors = members.items.map((member) => ({ id: member.user.id, displayName: member.user.display_name }))

  return <main className="administration-page audit-page" aria-labelledby="tenant-audit-title">
    <AuditHeading
      eyebrow={copy.eyebrow}
      id="tenant-audit-title"
      title={copy.title}
      description={copy.description}
    />
    <AuditFilters
      actions={tenantActions(locale)}
      locale={locale}
      actors={actors}
      filters={audit.filters}
      loadingActors={members.loadingMore}
      moreActors={Boolean(members.nextCursor)}
      onApply={audit.applyFilters}
      onLoadMoreActors={members.loadMore}
      onReset={audit.resetFilters}
    />
    <AuditTimeline audit={audit} locale={locale} timezone={organization.organization?.timezone ?? 'UTC'} />
  </main>
}


export function AuditHeading({ description, eyebrow, id, title }) {
  return <header className="administration-page-heading members-page-heading">
    <div className="administration-card-icon" aria-hidden="true"><Clock3 size={22} /></div>
    <div><p className="eyebrow">{eyebrow}</p><h1 id={id}>{title}</h1><p>{description}</p></div>
  </header>
}
