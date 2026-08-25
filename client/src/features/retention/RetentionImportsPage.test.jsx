import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { complianceApi } from '../compliance/api/complianceApi'
import { retentionApi } from './api/retentionApi'
import { RetentionImportsPage } from './RetentionImportsPage'

vi.mock('../compliance/api/complianceApi', () => ({ complianceApi: { listAcquisitions: vi.fn() } }))
vi.mock('./api/retentionApi', () => ({
  retentionApi: {
    listPolicies: vi.fn(), listReviews: vi.fn(), listHolds: vi.fn(), listImports: vi.fn(),
  },
}))

describe('RetentionImportsPage', () => {
  beforeEach(() => {
    retentionApi.listPolicies.mockResolvedValue({ items: [] })
    retentionApi.listReviews.mockResolvedValue({ items: [] })
    retentionApi.listHolds.mockResolvedValue({ items: [] })
    retentionApi.listImports.mockResolvedValue({ items: [] })
    complianceApi.listAcquisitions.mockResolvedValue({ items: [] })
  })

  it('rend l’import strictement déclaratif et sans sélecteur de fichier', async () => {
    render(<RetentionImportsPage session={{ capabilities: ['retention:read', 'imports:read', 'imports:declare'] }} />)
    await screen.findByRole('heading', { name: 'Politiques' })
    fireEvent.click(screen.getByRole('tab', { name: 'Déclarations d’import' }))
    expect(screen.getByText(/téléversement et le traitement du fichier/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Déclarer sans téléverser' })).toBeInTheDocument()
    expect(document.querySelector('input[type="file"]')).toBeNull()
  })
})
