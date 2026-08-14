import { Building2 } from '../../icons'
import { PlatformOrganizationList } from './components/PlatformOrganizationList'
import { ProvisionOrganizationForm } from './components/ProvisionOrganizationForm'
import { usePlatformOrganizations } from './hooks/usePlatformOrganizations'


export function PlatformOrganizationsPage({ createId, session }) {
  const organizations = usePlatformOrganizations()
  const canCreate = session.capabilities.includes('platform:organizations:create')
  const canManage = session.capabilities.includes('platform:organizations:manage')
  return <main className="administration-page platform-page" aria-labelledby="platform-page-title">
    <header className="administration-page-heading members-page-heading">
      <div className="administration-card-icon" aria-hidden="true"><Building2 size={22} /></div>
      <div><p className="eyebrow">Administration de la plateforme</p><h1 id="platform-page-title">Organisations</h1><p>Provisionnez les organisations et suivez uniquement leur invitation initiale.</p></div>
    </header>
    {canCreate && <ProvisionOrganizationForm createId={createId} onProvisioned={organizations.upsert} />}
    <PlatformOrganizationList canManage={canCreate} canManageStatus={canManage} createId={createId} organizations={organizations} onReconciled={organizations.upsert} />
  </main>
}
