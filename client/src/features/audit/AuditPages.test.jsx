import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { auditApi } from './api/auditApi'
import { PlatformAuditPage } from './PlatformAuditPage'
import { TenantAuditPage } from './TenantAuditPage'

vi.mock('./api/auditApi', () => ({
  auditApi: { listTenant: vi.fn(), listPlatform: vi.fn() },
}))
vi.mock('../organizations/hooks/useMembers', () => ({
  useMembers: () => ({
    items: [{ user: { id: 'actor-1', display_name: 'Gestionnaire' } }],
    nextCursor: null,
    loadingMore: false,
    loadMore: vi.fn(),
  }),
}))
vi.mock('../organizations/hooks/useOrganization', () => ({
  useOrganization: () => ({ organization: { timezone: 'America/Toronto' } }),
}))

const event = {
  id: 'event-1',
  occurred_at: '2026-08-09T15:00:00Z',
  action: 'membership.role_changed',
  entity_type: 'membership',
  entity_id: 'membership-1',
  actor: { kind: 'user', id: 'actor-1', display_name: 'Gestionnaire' },
  request_id: 'request-1',
  correlation_id: 'correlation-1',
  source: 'api',
  metadata: { previous_role: 'sales', new_role: 'manager', email: 'must-not-render@example.ca' },
  schema_version: 1,
}

const session = {
  user: { id: 'actor-1', display_name: 'Gestionnaire' },
  active_organization: { id: 'org-1', name: 'Entreprise Démonstration' },
}


describe('pages d’audit', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const page = {
      items: [event],
      next_cursor: null,
      occurred_from: '2026-07-10T15:00:00Z',
      occurred_to: '2026-08-09T15:00:00Z',
    }
    auditApi.listTenant.mockResolvedValue(page)
    auditApi.listPlatform.mockResolvedValue({ ...page, items: [{ ...event, action: 'organization.provisioned', entity_type: 'organization' }] })
  })

  it('affiche la chronologie locataire et seulement les métadonnées autorisées', async () => {
    render(<TenantAuditPage session={session} />)

    expect(screen.getByRole('heading', { name: 'Journal d’activité' })).toBeInTheDocument()
    expect(await screen.findByText('Rôle d’un membre modifié')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Afficher les détails' }))
    expect(screen.getByText('Ancien rôle')).toBeInTheDocument()
    expect(screen.getByText('Commercial')).toBeInTheDocument()
    expect(screen.queryByText('must-not-render@example.ca')).not.toBeInTheDocument()
    expect(screen.queryByText(/"previous_role"/)).not.toBeInTheDocument()
  })

  it('applique une nouvelle période sans stocker les filtres dans l’URL', async () => {
    render(<TenantAuditPage session={session} />)
    await screen.findByText('Rôle d’un membre modifié')
    fireEvent.click(screen.getByLabelText('7 jours'))
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))

    await waitFor(() => expect(auditApi.listTenant).toHaveBeenCalledTimes(2))
    const filters = auditApi.listTenant.mock.calls[1][0]
    expect(new Date(filters.occurredTo) - new Date(filters.occurredFrom)).toBe(7 * 24 * 60 * 60 * 1000)
    expect(window.location.search).toBe('')
  })

  it('utilise exclusivement le client plateforme dans la vue plateforme', async () => {
    render(<PlatformAuditPage session={session} />)
    expect(await screen.findByText('Organisation provisionnée')).toBeInTheDocument()
    expect(auditApi.listPlatform).toHaveBeenCalledOnce()
    expect(auditApi.listTenant).not.toHaveBeenCalled()
  })

  it('masque les métadonnées d’une version inconnue', async () => {
    auditApi.listTenant.mockResolvedValue({
      items: [{ ...event, schema_version: 99, action: 'future.action' }],
      next_cursor: null,
    })
    render(<TenantAuditPage session={session} />)
    expect(await screen.findByText('Événement non pris en charge')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Afficher les détails' }))
    expect(screen.getByText('Les détails de cette version ne peuvent pas être affichés.')).toBeInTheDocument()
    expect(screen.queryByText('Commercial')).not.toBeInTheDocument()
  })

  it('rend un changement d’étape Kanban avec ses métadonnées de workflow', async () => {
    auditApi.listTenant.mockResolvedValue({
      items: [{
        ...event,
        action: 'prospect.stage_changed',
        entity_type: 'prospect',
        metadata: {
          from_stage: 'qualifying',
          to_stage: 'qualified',
          from_version: 2,
          resulting_version: 3,
        },
      }],
      next_cursor: null,
    })

    render(<TenantAuditPage session={session} />)

    expect(await screen.findByText('Étape commerciale modifiée')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Afficher les détails' }))
    expect(screen.getByText('Étape précédente')).toBeInTheDocument()
    expect(screen.getByText('Qualification')).toBeInTheDocument()
    expect(screen.getByText('Nouvelle étape')).toBeInTheDocument()
    expect(screen.getByText('Qualifié')).toBeInTheDocument()
    expect(screen.getByText('2 → 3')).toBeInTheDocument()
  })
})
