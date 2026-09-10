import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { prospectApi } from './api/prospectApi'
import { TasksPage } from './TasksPage'

vi.mock('./api/prospectApi', () => ({
  prospectApi: { listTasks: vi.fn(), listDueReminders: vi.fn(), taskAction: vi.fn() },
}))

const task = {
  id: 'task-1', prospect_id: 'prospect-1', title: 'Rappeler Atelier Alpha', due_at: '2026-09-05T17:00:00Z',
  priority: 'high', status: 'open', version: 1, reminder_at: '2026-09-05T14:00:00Z',
  reminder_acknowledged_at: null, reminder_snoozed_until: null, is_overdue: true, assigned_membership_is_active: true,
}

describe('TasksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    prospectApi.listTasks.mockResolvedValue({ items: [task] })
    prospectApi.listDueReminders.mockResolvedValue({ items: [task] })
    prospectApi.taskAction.mockResolvedValue({})
  })

  it('charge les tâches et les rappels dus en parallèle puis accuse un rappel', async () => {
    render(<TasksPage session={{ active_organization: { locale: 'fr-CA', timezone: 'America/Toronto' } }} />)

    expect(await screen.findByRole('heading', { name: 'Mes tâches' })).toBeInTheDocument()
    expect(screen.getAllByText('Rappeler Atelier Alpha')).toHaveLength(2)
    fireEvent.click(screen.getByRole('button', { name: 'Accuser le rappel' }))

    await waitFor(() => expect(prospectApi.taskAction).toHaveBeenCalledWith(
      'task-1', 'acknowledge-reminder', expect.objectContaining({ version: 1 }),
    ))
  })
})
