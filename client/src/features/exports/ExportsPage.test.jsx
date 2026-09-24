import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exportApi } from './api/exportApi'
import { ExportsPage } from './ExportsPage'

vi.mock('./api/exportApi', () => ({ exportApi: { list: vi.fn(), create: vi.fn(), download: vi.fn(), listRules: vi.fn() } }))

describe('ExportsPage', () => {
  beforeEach(() => {
    exportApi.list.mockResolvedValue({ items: [], next_cursor: null })
    exportApi.create.mockResolvedValue({ id: 'new-export', status: 'queued' })
  })

  it('limits sales users to their own scope and submits a closed dataset', async () => {
    render(<ExportsPage session={{ capabilities: ['exports:create:self', 'prospects:read'], active_organization: { locale: 'en-CA' } }} />)
    await screen.findByText('No requests yet.')
    expect(screen.queryByRole('option', { name: 'Organization' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Prepare CSV' }))
    await waitFor(() => expect(exportApi.create).toHaveBeenCalledWith(
      { dataset: 'prospects', scope: 'self', filters: {} }, expect.any(String),
    ))
  })

  it('only offers a download for a ready artifact', async () => {
    exportApi.list.mockResolvedValue({ items: [
      { id: 'first', dataset: 'prospects', scope: 'self', status: 'queued', created_at: '2026-09-24T00:00:00Z' },
      { id: 'second', dataset: 'tasks', scope: 'self', status: 'ready', created_at: '2026-09-24T00:00:00Z' },
    ], next_cursor: null })
    render(<ExportsPage session={{ capabilities: ['exports:create:self'], active_organization: { locale: 'en-CA' } }} />)
    expect(await screen.findAllByRole('button', { name: 'Download' })).toHaveLength(1)
  })
})
