import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { axeViolations, formatViolations } from '../../../test/accessibility'
import { TaskPanel } from './TaskPanel'
import { taskDueState } from './taskPresentation'

const task = {
  id: 'task-1', title: 'Relancer Atelier Nord', due_at: '2026-09-06T14:00:00Z', priority: 'high', status: 'open', version: 1,
  reminder_at: null, reminder_acknowledged_at: null, reminder_snoozed_until: null, is_overdue: false, assigned_membership_is_active: true,
}

describe('TaskPanel', () => {
  it('crée une tâche avec son échéance et un rappel facultatif', async () => {
    const onCreate = vi.fn().mockResolvedValue(true)
    render(<TaskPanel tasks={[task]} locale="fr-CA" timezone="America/Toronto" canCreate submitting={false} onCreate={onCreate} onAction={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Titre de la tâche'), { target: { value: 'Préparer la proposition' } })
    fireEvent.change(screen.getByLabelText('Priorité'), { target: { value: 'urgent' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer la tâche' }))

    expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ title: 'Préparer la proposition', priority: 'urgent' }))
    expect(screen.getByText('Prochaine action')).toBeInTheDocument()
  })

  it('demande un motif pour annuler ou rouvrir une tâche', async () => {
    const onAction = vi.fn().mockResolvedValue(true)
    render(<TaskPanel tasks={[task]} locale="fr-CA" timezone="America/Toronto" canCreate={false} submitting={false} onCreate={vi.fn()} onAction={onAction} />)

    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    fireEvent.change(screen.getByLabelText('Motif'), { target: { value: 'Priorité commerciale modifiée' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))

    expect(onAction).toHaveBeenCalledWith(task, 'cancel', { reason: 'Priorité commerciale modifiée' })
  })

  it('calcule un retard sans le stocker', () => {
    expect(taskDueState({ ...task, is_overdue: true }, 'fr-CA').label).toBe('En retard')
  })

  it('ne présente aucune violation axe', async () => {
    const { container } = render(<TaskPanel tasks={[task]} locale="fr-CA" timezone="America/Toronto" canCreate submitting={false} onCreate={vi.fn()} onAction={vi.fn()} />)
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })
})
